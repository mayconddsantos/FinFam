import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
from datetime import date

# Configuração da página
st.set_page_config(page_title="Finanças da Família", page_icon="💰", layout="centered")

# Conexão com o banco de dados Supabase
def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

# Função para validar login com PIN
def autenticar_usuario(pin_digitado):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM usuarios WHERE pin = %s", (pin_digitado,))
    usuario = cur.fetchone()
    cur.close()
    conn.close()
    return usuario

# Controle de sessão
if "usuario" not in st.session_state:
    st.session_state.usuario = None

# TELA DE LOGIN
if st.session_state.usuario is None:
    st.title("💰 Finanças da Família")
    st.write("Digite seu PIN de acesso para entrar:")
    pin = st.text_input("PIN", type="password", max_chars=10)
    if st.button("Entrar", use_container_width=True):
        user = autenticar_usuario(pin)
        if user:
            st.session_state.usuario = {"id": user[0], "nome": user[1]}
            st.rerun()
        else:
            st.error("PIN incorreto. Tente novamente.")
    st.stop()

# USUÁRIO LOGADO
usuario_id = st.session_state.usuario["id"]
usuario_nome = st.session_state.usuario["nome"]

col_topo1, col_topo2 = st.columns([4, 1])
col_topo1.title(f"Olá, {usuario_nome} 👋")
if col_topo2.button("Sair"):
    st.session_state.usuario = None
    st.rerun()

# ABAS DO APLICATIVO
aba_lancar, aba_resumo, aba_historico = st.tabs(["➕ Lançar", "📊 Resumo", "📋 Histórico"])

# ABA 1: NOVO LANÇAMENTO
with aba_lancar:
    st.subheader("Novo Registro")
    
    # Tipo e Natureza fora do form para atualizar as categorias instantaneamente
    col_r1, col_r2 = st.columns(2)
    tipo = col_r1.radio("Tipo", ["Despesa", "Receita"], horizontal=True)
    natureza = col_r2.radio("Natureza", ["Variável", "Fixo"], horizontal=True)
    
    categorias_despesa = [
        "Alimentação", "Cartão de Crédito", "Moradia", "Transporte", "Saúde", "Lazer", "Contas", "Compras", "Outros", "Educação", "Assinaturas"
    ]
    categorias_receita = ["Salário", "Mariana Rui", "Encordoamentos", "Arbitragem", "Tenis/Padel", "Investimentos", "Outros"]
    categorias = categorias_despesa if tipo == "Despesa" else categorias_receita

    with st.form("form_transacao", clear_on_submit=True):
        valor = st.number_input("Valor (R$)", min_value=0.01, format="%.2f", step=10.0)
        categoria = st.selectbox("Categoria", categorias)
        descricao = st.text_input("Descrição (opcional)", placeholder="Ex: Supermercado, Conta de luz...")
        data_lancamento = st.date_input("Data", value=date.today())
        
        submitted = st.form_submit_button("Salvar Lançamento", use_container_width=True, type="primary")
        if submitted:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO transacoes (data, tipo, natureza, categoria, descricao, valor, usuario_id) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (data_lancamento, tipo, natureza, categoria, descricao, valor, usuario_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            st.success(f"{tipo} ({natureza}) de R$ {valor:.2f} salva com sucesso!")

# Carrega dados do banco para as abas de Resumo e Histórico
conn = get_connection()
query = """
    SELECT t.id, t.data, t.tipo, COALESCE(t.natureza, 'Variável') as natureza, 
           t.categoria, t.descricao, t.valor, u.nome as responsavel
    FROM transacoes t
    JOIN usuarios u ON t.usuario_id = u.id
    ORDER BY t.data DESC, t.id DESC
"""
df = pd.read_sql(query, conn)
conn.close()

# ABA 2: RESUMO E GRÁFICOS
with aba_resumo:
    if df.empty:
        st.info("Nenhum lançamento registrado ainda.")
    else:
        df["data"] = pd.to_datetime(df["data"])
        hoje = date.today()
        
        col_m, col_a = st.columns(2)
        mes_sel = col_m.selectbox("Mês", range(1, 13), index=hoje.month - 1)
        ano_sel = col_a.number_input("Ano", value=hoje.year, step=1)
        
        df_mes = df[(df["data"].dt.month == mes_sel) & (df["data"].dt.year == ano_sel)]
        
        receitas = df_mes[df_mes["tipo"] == "Receita"]["valor"].sum()
        despesas = df_mes[df_mes["tipo"] == "Despesa"]["valor"].sum()
        saldo = receitas - despesas
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Receitas", f"R$ {receitas:,.2f}")
        c2.metric("Despesas", f"R$ {despesas:,.2f}")
        c3.metric("Saldo", f"R$ {saldo:,.2f}")
        
        st.divider()
        df_despesas = df_mes[df_mes["tipo"] == "Despesa"]
        if not df_despesas.empty:
            st.subheader("Despesas por Categoria")
            fig = px.pie(df_despesas, values="valor", names="categoria", hole=0.4)
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Despesas por Natureza")
            fig_nat = px.pie(
                df_despesas, values="valor", names="natureza", hole=0.4, 
                color_discrete_sequence=["#FF6B6B", "#4ECDC4"]
            )
            fig_nat.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_nat, use_container_width=True)
        else:
            st.write("Nenhuma despesa registrada neste mês.")

# ABA 3: HISTÓRICO E EXCLUSÃO
with aba_historico:
    if df.empty:
        st.info("Nenhum lançamento registrado ainda.")
    else:
        st.subheader("Últimos Lançamentos")
        for _, row in df.head(30).iterrows():
            icone = "🔴" if row["tipo"] == "Despesa" else "🟢"
            data_fmt = pd.to_datetime(row["data"]).strftime("%d/%m/%Y")
            desc = f" - {row['descricao']}" if row["descricao"] else ""
            
            col_info, col_del = st.columns([5, 1])
            col_info.markdown(
                f"{icone} **{row['categoria']}** `[{row['natureza']}]`{desc}  \n"
                f"R$ {row['valor']:.2f} • *{data_fmt} ({row['responsavel']})*"
            )
            
            if col_del.button("🗑️", key=f"del_{row['id']}", help="Excluir registro"):
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM transacoes WHERE id = %s", (int(row["id"]),))
                conn.commit()
                cur.close()
                conn.close()
                st.rerun()
            st.divider()
