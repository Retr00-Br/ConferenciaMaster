import datetime
import pandas as pd
from supabase import create_client, Client

# --- CREDENCIAIS DO SUPABASE ---
SUPABASE_URL = "https://taycbigozolngeyalhvf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRheWNiaWdvem9sbmdleWFsaHZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAxODM2NjYsImV4cCI6MjEwNTc1OTY2Nn0.OvB92NqBuKwvJlrrLhoNfY1-8SJ8WD4GTwmSartRbYk"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def carregar_planilha_pedidos(caminho_excel_ou_buffer):
    """
    Lê a planilha Excel e insere/atualiza na tabela pedidosbase.
    """
    df = pd.read_excel(caminho_excel_ou_buffer, sheet_name=0)
    df = df.dropna(subset=['Pedido']).drop_duplicates(subset=['Pedido'])

    dados_para_inserir = []
    for _, row in df.iterrows():
        val_pedido = str(row['Pedido']).strip()

        try:
            num_pedido = int(float(val_pedido))
        except ValueError:
            digitos = ''.join(filter(str.isdigit, val_pedido))
            if digitos:
                num_pedido = int(digitos)
            else:
                continue

        dados_para_inserir.append({
            "pedido": num_pedido,
            "cliente": str(row['Cliente']) if pd.notna(row['Cliente']) else "",
            "datapedido": pd.to_datetime(row['Aberto Em']).strftime('%Y-%m-%d') if pd.notna(
                row['Aberto Em']) else datetime.date.today().isoformat(),
            "sku": int(row['Linhas']) if pd.notna(row['Linhas']) else 0
        })

    if not dados_para_inserir:
        return None

    resposta = supabase.table("pedidosbase").upsert(
        dados_para_inserir,
        on_conflict="pedido"
    ).execute()

    return resposta


def buscar_pedido(numero_pedido: int):
    """
    Busca um pedido na tabela pedidosbase pelo número do Pedido.
    """
    try:
        resposta = supabase.table("pedidosbase").select("*").eq("pedido", numero_pedido).execute()
        if resposta.data and len(resposta.data) > 0:
            return resposta.data[0]
        return None
    except Exception as e:
        raise Exception(f"Erro ao consultar o pedido {numero_pedido} no Supabase: {str(e)}")


def salvar_conferencia(id_pedido: int, conferente: str, volume: int, pallets: int, lista_erros: list, obs: str):
    """
    Salva os registros de conferência na tabela conferenciaerros.
    Se houver múltiplos erros cadastrados, insere cada erro como uma linha mantendo idpedido, conferente, volume e pallets.
    Se não houver erros (linhas_erro = 0), salva apenas um registro de conferência limpa.
    """
    dados_para_inserir = []
    data_hoje = datetime.date.today().isoformat()

    if lista_erros:
        for erro in lista_erros:
            dados_para_inserir.append({
                "idpedido": id_pedido,
                "conferente": conferente,
                "volume": volume,
                "pallets": pallets,
                "dataconferencia": data_hoje,
                "linhaserro": len(lista_erros),
                "itemerrado": erro.get("item", ""),
                "tipoerro": erro.get("tipo", "Outro"),
                "observacao": obs
            })
    else:
        # Conferência sem erros
        dados_para_inserir.append({
            "idpedido": id_pedido,
            "conferente": conferente,
            "volume": volume,
            "pallets": pallets,
            "dataconferencia": data_hoje,
            "linhaserro": 0,
            "itemerrado": "Nenhum",
            "tipoerro": "Nenhum",
            "observacao": obs
        })

    resposta = supabase.table("conferenciaerros").insert(dados_para_inserir).execute()
    return resposta


def buscar_relatorio_conferencias():
    """
    Busca conferências com Join em pedidosbase, incluindo os campos de volume e pallets.
    """
    try:
        try:
            resposta = supabase.table("conferenciaerros").select(
                "idconferencia, idpedido, conferente, volume, pallets, dataconferencia, linhaserro, itemerrado, tipoerro, observacao, pedidosbase(pedido, cliente, sku)"
            ).execute()
        except Exception:
            resposta = supabase.table("conferenciaerros").select(
                "idconferencia, idpedido, conferente, dataconferencia, linhaserro, itemerrado, tipoerro, observacao, pedidosbase(pedido, cliente, sku)"
            ).execute()

        if resposta.data:
            registros = []
            for item in resposta.data:
                pedido_info = item.get("pedidosbase") or {}
                sku_total = pedido_info.get("sku", 0)
                linhas_erro = item.get("linhaserro", 0)
                linhas_certas = max(0, sku_total - linhas_erro)

                registros.append({
                    "ID Conferência": item.get("idconferencia"),
                    "Pedido": pedido_info.get("pedido"),
                    "Cliente": pedido_info.get("cliente"),
                    "Volume": item.get("volume", 1),
                    "Pallets": item.get("pallets", 0),
                    "Total Linhas": sku_total,
                    "Linhas Certas": linhas_certas,
                    "Linhas Erradas": linhas_erro,
                    "Conferente": item.get("conferente"),
                    "Data Conferência": item.get("dataconferencia"),
                    "Tipo de Erro": item.get("tipoerro"),
                    "Item Errado": item.get("itemerrado"),
                    "Observação": item.get("observacao")
                })
            return pd.DataFrame(registros)
        return pd.DataFrame()
    except Exception as e:
        raise Exception(f"Erro ao buscar relatórios: {str(e)}")


def limpar_dados_antigos(dias_retencao: int = 7):
    """
    Remove registros antigos mantendo a base enxuta.
    """
    data_limite = (datetime.date.today() - datetime.timedelta(dias=dias_retencao)).isoformat()

    res_erros = supabase.table("conferenciaerros").delete().lt("dataconferencia", data_limite).execute()
    res_pedidos = supabase.table("pedidosbase").delete().lt("datapedido", data_limite).execute()

    return {
        "conferencias_removidas": len(res_erros.data) if res_erros.data else 0,
        "pedidos_removidos": len(res_pedidos.data) if res_pedidos.data else 0,
        "data_corte": data_limite
    }
