import sys
import os
import io
import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Database import (
    buscar_pedido,
    salvar_conferencia,
    carregar_planilha_pedidos,
    limpar_dados_antigos,
    buscar_relatorio_conferencias
)

st.set_page_config(page_title="ConferênciaMaster", layout="wide", page_icon="📦")
st.title("📦 ConferênciaMaster — Gestão de divergências")

aba1, aba2, aba3, aba4 = st.tabs([
    "🔍 Lançamento por Bipagem",
    "📊 Dashboard & Exportação",
    "📂 Carga de Planilha",
    "⚙️ Manutenção & Backup"
])

# ---------------------------------------------------------
# TAB 1: LANÇAMENTO / BIPAGEM
# ---------------------------------------------------------
with aba1:
    st.header("Bipagem / Validação do Pedido")
    st.caption("Passe o leitor de código de barras ou digite o número do pedido e pressione Enter.")

    num_pedido_input = st.number_input("Digite ou Bipe o Número do Pedido:", min_value=1, step=1, value=None)

    if num_pedido_input:
        dados_pedido = buscar_pedido(int(num_pedido_input))

        if dados_pedido:
            st.success(f"**Cliente:** {dados_pedido['cliente']} | **Total de Linhas (SKU):** {dados_pedido['sku']}")

            # Inicializa a lista de erros na sessão caso não exista
            if "lista_erros" not in st.session_state:
                st.session_state.lista_erros = []

            conferente = st.text_input("Nome do Conferente *", key="input_conferente")

            c_vol, c_pal = st.columns(2)
            with c_vol:
                volume = st.number_input(
                    "Volume / Nº da Caixa *",
                    min_value=1,
                    step=1,
                    value=1,
                    help="Digite o número do volume ou da caixa conferida."
                )
            with c_pal:
                pallets = st.number_input(
                    "Quantidade de Pallets *",
                    min_value=0,
                    step=1,
                    value=1,
                    help="Informe a quantidade de pallets conferidos."
                )

            st.divider()
            st.subheader("⚠️ Registro de Erros / Divergências")
            st.caption("Adicione uma ou mais linhas para cada item divergente encontrado neste pedido.")

            # Formulário dinâmico para adicionar linhas de erros
            col_item, col_tipo, col_btn = st.columns([3, 3, 1])
            with col_item:
                novo_item = st.text_input("Código / Descrição do Item Errado", key="novo_item_input")
            with col_tipo:
                novo_tipo = st.selectbox(
                    "Tipo de Erro",
                    [
                        "Item Invertido",
                        "Quantidade a Maior",
                        "Quantidade a Menor",
                        "Embalagem Avariada",
                        "Lote/Validade Divergente",
                        "Outro"
                    ],
                    key="novo_tipo_input"
                )
            with col_btn:
                st.write("")
                st.write("")
                if st.button("➕ Adicionar Erro"):
                    if novo_item.strip():
                        st.session_state.lista_erros.append({
                            "item": novo_item.strip(),
                            "tipo": novo_tipo
                        })
                        st.success(f"Item '{novo_item}' adicionado!")
                        st.rerun()
                    else:
                        st.warning("Informe a descrição do item antes de adicionar.")

            # Exibe a lista de erros já adicionados
            if st.session_state.lista_erros:
                st.write("**Lista de Erros Adicionados:**")
                for index, err in enumerate(st.session_state.lista_erros):
                    col_detalhe, col_remover = st.columns([5, 1])
                    col_detalhe.info(f"**Linha {index + 1}:** {err['item']} — *{err['tipo']}*")
                    if col_remover.button("❌ Remover", key=f"btn_rem_{index}"):
                        st.session_state.lista_erros.pop(index)
                        st.rerun()

            linhas_erro = len(st.session_state.lista_erros)
            linhas_certas = max(0, int(dados_pedido['sku']) - linhas_erro)
            st.info(f"📊 **Linhas Certas:** {linhas_certas} | **Linhas Erradas:** {linhas_erro}")

            obs = st.text_area("Observação (Opcional)", key="input_obs")

            if st.button("💾 Salvar Conferência Completa", type="primary"):
                if not conferente:
                    st.error("Preencha o nome do conferente para prosseguir!")
                else:
                    salvar_conferencia(
                        id_pedido=dados_pedido['idpedido'],
                        conferente=conferente,
                        volume=int(volume),
                        pallets=int(pallets),
                        lista_erros=st.session_state.lista_erros,
                        obs=obs
                    )
                    st.success("Conferência cadastrada com sucesso!")
                    # Limpa a lista de erros após salvar
                    st.session_state.lista_erros = []
                    st.rerun()
        else:
            st.warning("Pedido não encontrado no banco de dados. Faça a importação da planilha na aba 'Carga de Planilha'.")

# ---------------------------------------------------------
# TAB 2: DASHBOARD E EXPORTAÇÃO
# ---------------------------------------------------------
with aba2:
    st.header("📊 Dashboard de Performance e Relatórios")

    df_rel = buscar_relatorio_conferencias()

    if not df_rel.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Conferências", len(df_rel))
        c2.metric("Total Linhas Erradas", int(df_rel["Linhas Erradas"].sum()))
        c3.metric("Total Linhas Certas", int(df_rel["Linhas Certas"].sum()))
        c4.metric("Total Pallets", int(df_rel["Pallets"].sum()))

        st.divider()

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Ocorrências por Tipo de Erro")
            st.bar_chart(df_rel["Tipo de Erro"].value_counts())

        with col_g2:
            st.subheader("Linhas Erradas por Conferente")
            st.bar_chart(df_rel.groupby("Conferente")["Linhas Erradas"].sum())

        st.divider()
        st.dataframe(df_rel, use_container_width=True)

        exp1, exp2 = st.columns(2)
        with exp1:
            csv_data = df_rel.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exportar CSV", data=csv_data, file_name="conferencias.csv", mime="text/csv")

        with exp2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_rel.to_excel(writer, index=False, sheet_name='Relatorio')
            st.download_button("📊 Exportar Excel (.xlsx)", data=buffer.getvalue(), file_name="conferencias.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Nenhuma conferência registrada até o momento.")

# ---------------------------------------------------------
# TAB 3: CARGA DA PLANILHA
# ---------------------------------------------------------
with aba3:
    st.header("📂 Importação da Planilha de Pedidos")
    arquivo = st.file_uploader("Selecione a planilha (.xlsx)", type=["xlsx"])

    if arquivo is not None and st.button("Processar Planilha"):
        try:
            carregar_planilha_pedidos(arquivo)
            st.success("Planilha processada com sucesso! Pedidos inseridos/atualizados sem duplicação.")
        except Exception as e:
            st.error(f"Erro ao processar: {str(e)}")

# ---------------------------------------------------------
# TAB 4: MANUTENÇÃO
# ---------------------------------------------------------
with aba4:
    st.header("⚙️ Limpeza Semanal do Banco")
    senha = st.text_input("Senha de Manutenção:", type="password")

    if senha == "Backup" and st.button("Executar Limpeza (> 7 Dias)"):
        res = limpar_dados_antigos(7)
        st.success(
            f"Limpeza concluída! Data corte: {res['data_corte']} | Removidos: {res['conferencias_removidas']} conferências e {res['pedidos_removidos']} pedidos.")
