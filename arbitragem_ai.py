import streamlit as st
import json
import os
import time
import random
from datetime import datetime
from urllib.parse import quote
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid

# ==============================================
# CONFIGURAÇÕES
# ==============================================
CONFIG = {
    "pix_nome_recebedor": "Seu Nome Completo",
    "pix_chave": "sua.chave.pix@exemplo.com",
    "whatsapp_admin": "5521997524939",
    "email_remetente": "",
    "senha_app_email": "",
    "smtp_servidor": "smtp.gmail.com",
    "smtp_porta": 587,
    "senha_admin": "admin123",
    "taxa_media_corretora_perc": 0.1
}

ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_SISTEMA = "sistema.json"
ARQUIVO_HISTORICO = "historico_oportunidades.json"
ARQUIVO_CODIGOS_RECUPERACAO = "codigos_recuperacao.json"
ARQUIVO_HISTORICO_OPERACOES = "historico_operacoes.json"
ARQUIVO_SALDOS = "saldos_corretoras.json"

PLANOS = {
    "Gratuito": {
        "preco": 0.0,
        "moedas": 3,
        "atualizacao_segundos": 120,
        "alertas_email": False,
        "alertas_whatsapp": False,
        "corretoras": ["Binance", "Bybit"],
        "modo_avancado": False,
        "bot_operacional": False
    },
    "Pro": {
        "preco": 49.90,
        "moedas": 50,
        "atualizacao_segundos": 60,
        "alertas_email": True,
        "alertas_whatsapp": True,
        "corretoras": ["Binance", "Bybit", "KuCoin", "OKX"],
        "modo_avancado": True,
        "bot_operacional": True
    },
    "Premium": {
        "preco": 99.90,
        "moedas": 9999,
        "atualizacao_segundos": 15,
        "alertas_email": True,
        "alertas_whatsapp": True,
        "corretoras": ["Binance", "Bybit", "KuCoin", "OKX", "Gate.io", "Mercado Bitcoin"],
        "modo_avancado": True,
        "bot_operacional": True
    }
}

MOEDAS_MONITORADAS = [
    "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "DOT", "AVAX", "MATIC", "LINK",
    "ATOM", "UNI", "LTC", "BCH", "FIL", "NEAR", "FTM", "SAND", "MANA", "AXS"
]

CORRETORAS_DISPONIVEIS = ["Binance", "Bybit", "KuCoin", "OKX", "Gate.io", "Mercado Bitcoin", "Coinbase", "Kraken"]

# ==============================================
# FUNÇÕES DE ARQUIVO
# ==============================================
def carregar_json(caminho, padrao={}):
    if not os.path.exists(caminho):
        return padrao
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return padrao

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

dados_sistema = carregar_json(ARQUIVO_SISTEMA, {})
if dados_sistema:
    CONFIG.update(dados_sistema)

# ==============================================
# SALDOS DAS CORRETORAS — EVOLUÇÃO
# ==============================================
def inicializar_saldos_usuario(email, saldo_inicial=1000.0):
    saldos = carregar_json(ARQUIVO_SALDOS, {})
    if email not in saldos:
        saldos[email] = {
            corretora: {
                "saldo_atual": saldo_inicial,
                "saldo_inicial": saldo_inicial,
                "lucro_total": 0.0,
                "qtd_operacoes": 0,
                "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
            for corretora in CORRETORAS_DISPONIVEIS
        }
        salvar_json(ARQUIVO_SALDOS, saldos)
    return saldos[email]

def atualizar_saldo_apos_operacao(email, corretora_compra, corretora_venda, valor_investido, lucro_liquido_perc):
    saldos = carregar_json(ARQUIVO_SALDOS, {})
    if email not in saldos:
        inicializar_saldos_usuario(email)
        saldos = carregar_json(ARQUIVO_SALDOS, {})
    
    lucro_valor = valor_investido * (lucro_liquido_perc / 100)
    
    saldos[email][corretora_compra]["saldo_atual"] -= valor_investido
    saldos[email][corretora_venda]["saldo_atual"] += valor_investido + lucro_valor
    saldos[email][corretora_venda]["lucro_total"] += lucro_valor
    saldos[email][corretora_venda]["qtd_operacoes"] += 1
    saldos[email][corretora_venda]["ultima_atualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    salvar_json(ARQUIVO_SALDOS, saldos)
    return lucro_valor

def obter_saldos_usuario(email):
    saldos = carregar_json(ARQUIVO_SALDOS, {})
    return saldos.get(email, {})

# ==============================================
# NAVEGAÇÃO
# ==============================================
def exibir_logo_principal(largura=250):
    st.markdown("<h1 style='text-align: center; color: #22c55e;'>ARBITRAGEM AI</h1>", unsafe_allow_html=True)

def botao_voltar_menu():
    if st.button("⬅️ Voltar ao Menu Principal"):
        st.session_state["pagina"] = "inicio"
        st.rerun()

def botao_sair_conta():
    if st.sidebar.button("🚪 Sair da Conta", type="secondary"):
        for chave in list(st.session_state.keys()):
            if chave not in ["pagina"]:
                del st.session_state[chave]
        st.session_state["pagina"] = "inicio"
        st.rerun()

# ==============================================
# E-MAIL
# ==============================================
def enviar_email(destinatario, assunto, mensagem_html):
    try:
        remetente = CONFIG.get("email_remetente", "")
        senha = CONFIG.get("senha_app_email", "")
        servidor = CONFIG.get("smtp_servidor", "smtp.gmail.com")
        porta = CONFIG.get("smtp_porta", 587)
        
        if not remetente or not senha:
            return False, "⚠️ Configure o e-mail no Painel de Administração"
        
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destinatario
        msg["Subject"] = assunto
        msg.attach(MIMEText(mensagem_html, "html"))
        
        with smtplib.SMTP(servidor, porta) as s:
            s.starttls()
            s.login(remetente, senha)
            s.send_message(msg)
        return True, "✅ E-mail enviado!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def enviar_email_aprovacao_plano(email_usuario, nome_usuario, plano):
    assunto = f"✅ Seu Plano {plano} foi Ativado — Arbitragem AI"
    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0;padding:20px;background:#f8f9fa;">
        <div style="background:white;padding:30px;border-radius:12px;border-top:4px solid #22c55e;">
            <h2 style="color:#22c55e;margin-top:0;">🎉 Parabéns, {nome_usuario}!</h2>
            <p>Seu pagamento foi aprovado e seu plano está <strong>ATIVO</strong>!</p>
            <div style="background:#f0fdf4;padding:20px;border-radius:8px;margin:20px 0;">
                <p style="font-size:18px;margin:0;"><strong>Plano:</strong> {plano}</p>
                <p style="font-size:16px;margin:10px 0 0 0;">Acesse o app e comece a monitorar!</p>
            </div>
            <p>⚠️ Confirme sempre os preços na corretora antes de operar.</p>
            <p style="margin-top:30px;color:#888;font-size:12px;">Equipe Arbitragem AI</p>
        </div>
    </body>
    </html>
    """
    return enviar_email(email_usuario, assunto, html)

# ==============================================
# RECUPERAÇÃO DE SENHA
# ==============================================
def gerar_codigo_recuperacao(email):
    codigo = ''.join([str(random.randint(0,9)) for _ in range(6)])
    codigos = carregar_json(ARQUIVO_CODIGOS_RECUPERACAO, {})
    codigos[email] = {"codigo": codigo, "expira_em": datetime.now().timestamp()+900}
    salvar_json(ARQUIVO_CODIGOS_RECUPERACAO, codigos)
    return codigo

def verificar_codigo(email, digitado):
    codigos = carregar_json(ARQUIVO_CODIGOS_RECUPERACAO, {})
    if email not in codigos: return False
    d = codigos[email]
    if d["codigo"] == digitado and datetime.now().timestamp() < d["expira_em"]:
        del codigos[email]
        salvar_json(ARQUIVO_CODIGOS_RECUPERACAO, codigos)
        return True
    return False

# ==============================================
# BOT DE OPERAÇÃO — SIMULADO
# ==============================================
def verificar_chaves_corretoras(email, compra_em, venda_em):
    usuarios = carregar_json(ARQUIVO_USUARIOS, {})
    if email not in usuarios: return False, "Usuário não encontrado"
    apis = usuarios[email].get("apis_corretoras", {})
    if compra_em not in apis: return False, f"⚠️ Chave da {compra_em} não configurada!"
    if venda_em not in apis: return False, f"⚠️ Chave da {venda_em} não configurada!"
    if not apis[compra_em].get("api_key") or not apis[compra_em].get("api_secret"):
        return False, f"⚠️ Chaves da {compra_em} incompletas!"
    if not apis[venda_em].get("api_key") or not apis[venda_em].get("api_secret"):
        return False, f"⚠️ Chaves da {venda_em} incompletas!"
    return True, "✅ Chaves verificadas!"

def registrar_operacao(email, op, valor_investido, status="simulada"):
    hist = carregar_json(ARQUIVO_HISTORICO_OPERACOES, [])
    lucro_valor = valor_investido * (op["lucro_liquido_perc"] / 100)
    
    operacao = {
        "id": str(uuid.uuid4())[:8],
        "email": email,
        "moeda": op["moeda"],
        "comprar_em": op["comprar_em"],
        "vender_em": op["vender_em"],
        "preco_compra": op["preco_compra"],
        "preco_venda": op["preco_venda"],
        "valor_investido": valor_investido,
        "lucro_perc": op["lucro_liquido_perc"],
        "lucro_valor": lucro_valor,
        "status": status,
        "hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "modo": "automático" if st.session_state.get("bot_ativo") else "manual"
    }
    hist.insert(0, operacao)
    salvar_json(ARQUIVO_HISTORICO_OPERACOES, hist[:500])
    
    if status == "executada":
        atualizar_saldo_apos_operacao(
            email, op["comprar_em"], op["vender_em"],
            valor_investido, op["lucro_liquido_perc"]
        )
    return operacao

def executar_operacao(op, email, valor_investido=100.0):
    ok, msg = verificar_chaves_corretoras(email, op["comprar_em"], op["vender_em"])
    if not ok: return False, msg
    
    sucesso = random.random() > 0.10
    
    if sucesso:
        registrar_operacao(email, op, valor_investido, "executada")
        return True, f"""✅ OPERAÇÃO SIMULADA CONCLUÍDA!
💰 {op['moeda']}
✅ Compra na {op['comprar_em']}
📤 Venda na {op['vender_em']}
📈 Lucro: {op['lucro_liquido_perc']:.2f}% | R$ {valor_investido * (op['lucro_liquido_perc']/100):.2f}
⚠️ *Simulação — sem execução real no mercado*"""
    else:
        registrar_operacao(email, op, valor_investido, "falhou")
        return False, "❌ Preço mudou ou liquidez insuficiente — tente novamente"

# ==============================================
# SCANNER
# ==============================================
def gerar_preco_simulado(moeda, corretora, variacao=0.008):
    base = {"BTC":63420.50,"ETH":3218.90,"SOL":142.85,"XRP":0.52,"ADA":0.45,"DOGE":0.12}.get(moeda,1.0)
    seed = abs(hash(f"{moeda}-{corretora}-{datetime.now().strftime('%Y%m%d%H%M')}"))%1000/1000
    fator = 1 + (seed-0.5)*2*variacao
    return round(base*fator, 6 if base<1 else 2)

def calcular_lucro_liquido(pc, pv, taxa=None):
    if taxa is None: taxa = CONFIG["taxa_media_corretora_perc"]
    t_compra = pc*(taxa/100)
    t_venda = pv*(taxa/100)
    bruto = pv - pc
    liquido = bruto - t_compra - t_venda
    return {
        "lucro_bruto_perc": (bruto/pc*100) if pc>0 else 0,
        "lucro_liquido_perc": (liquido/pc*100) if pc>0 else 0
    }

def escanear_oportunidades(corretoras, moedas, min_lucro=0.5):
    ops = []
    for m in moedas:
        precos = {c: gerar_preco_simulado(m,c) for c in corretoras}
        for compra in corretoras:
            for venda in corretoras:
                if compra==venda: continue
                pc, pv = precos[compra], precos[venda]
                if pv<=pc: continue
                calc = calcular_lucro_liquido(pc, pv)
                if calc["lucro_liquido_perc"] < min_lucro: continue
                ops.append({
                    "moeda":m, "comprar_em":compra, "vender_em":venda,
                    "preco_compra":pc, "preco_venda":pv, **calc
                })
    return sorted(ops, key=lambda x:x["lucro_liquido_perc"], reverse=True)

# ==============================================
# INICIALIZAÇÃO
# ==============================================
st.set_page_config(page_title="Arbitragem AI", layout="wide")

for chave, padrao in [
    ("usuario", None), ("email_usuario", None), ("logado", False),
    ("admin_logado", False), ("pagina_recuperacao", "solicitar_email"),
    ("bot_ativo", False), ("ultima_execucao_bot", None)
]:
    if chave not in st.session_state:
        st.session_state[chave] = padrao

usuarios = carregar_json(ARQUIVO_USUARIOS, {})

# ==============================================
# TELA DE LOGIN
# ==============================================
def tela_login():
    exibir_logo_principal()
    st.subheader("Análise inteligente de oportunidades entre corretoras")
    st.warning("⚠️ Apenas análise e simulação. Não é recomendação de investimento.")
    st.markdown("---")
    
    entrar, cadastrar, recuperar = st.tabs(["Entrar", "Criar Conta", "Recuperar Senha"])
    
    with entrar:
        ident = st.text_input("E-mail ou Usuário", key="login_id")
        senha = st.text_input("Senha", type="password", key="login_senha")
        if st.button("ENTRAR", type="primary"):
            achou = None
            email_achou = None
            for e, d in usuarios.items():
                if e==ident or d.get("nome_usuario")==ident:
                    if d.get("senha")==senha:
                        achou = d
                        email_achou = e
                        break
            if achou:
                if achou.get("plano_ativo") or achou.get("plano")=="Gratuito":
                    st.session_state["usuario"] = achou
                    st.session_state["email_usuario"] = email_achou
                    st.session_state["logado"] = True
                    inicializar_saldos_usuario(email_achou)
                    st.rerun()
                else:
                    st.warning("Aguardando aprovação do pagamento.")
            else:
                st.error("Dados incorretos!")
    
    with cadastrar:
        email_novo = st.text_input("Seu E-mail", key="cad_email")
        usuario_novo = st.text_input("Nome de Usuário", key="cad_usuario")
        senha1 = st.text_input("Criar Senha", type="password", key="cad_senha1")
        senha2 = st.text_input("Repetir Senha", type="password", key="cad_senha2")
        if st.button("CRIAR CONTA", type="primary"):
            if email_novo in usuarios:
                st.error("E-mail já cadastrado!")
            elif any(d.get("nome_usuario")==usuario_novo for d in usuarios.values()):
                st.error("Usuário já em uso!")
            elif senha1 != senha2:
                st.error("Senhas não coincidem!")
            elif len(senha1) < 4:
                st.error("Senha muito curta!")
            else:
                usuarios[email_novo] = {
                    "nome_usuario": usuario_novo, "senha": senha1,
                    "plano": "Gratuito", "plano_escolhido": "Gratuito",
                    "plano_ativo": True, "status_pagamento": "aprovado",
                    "data_cadastro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "apis_corretoras": {}
                }
                salvar_json(ARQUIVO_USUARIOS, usuarios)
                inicializar_saldos_usuario(email_novo)
                st.session_state["usuario"] = usuarios[email_novo]
                st.session_state["email_usuario"] = email_novo
                st.session_state["logado"] = True
                st.success("Conta criada! 🎉")
                st.rerun()
    
    with recuperar:
        if st.session_state["pagina_recuperacao"] == "solicitar_email":
            email_rec = st.text_input("Digite seu e-mail cadastrado")
            if st.button("ENVIAR CÓDIGO", type="primary"):
                if email_rec in usuarios:
                    cod = gerar_codigo_recuperacao(email_rec)
                    ass = "🔐 Código de Recuperação — Arbitragem AI"
                    html = f"<p>Seu código: <strong style='font-size:24px;letter-spacing:4px;'>{cod}</strong></p><p>Válido por 15 min.</p>"
                    ok, msg = enviar_email(email_rec, ass, html)
                    if ok:
                        st.session_state["email_recuperacao"] = email_rec
                        st.session_state["pagina_recuperacao"] = "digitar_codigo"
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("E-mail não encontrado!")
        elif st.session_state["pagina_recuperacao"] == "digitar_codigo":
            email_rec = st.session_state["email_recuperacao"]
            st.info(f"Código enviado para {email_rec}")
            cod_digitado = st.text_input("Digite o código de 6 dígitos", max_chars=6)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("REENVIAR"):
                    cod = gerar_codigo_recuperacao(email_rec)
                    enviar_email(email_rec, "🔐 Código de Recuperação", f"<p>{cod}</p>")
                    st.success("Reenviado!")
            with c2:
                if st.button("VERIFICAR", type="primary"):
                    if verificar_codigo(email_rec, cod_digitado):
                        st.session_state["pagina_recuperacao"] = "nova_senha"
                        st.rerun()
                    else:
                        st.error("Código inválido!")
            if st.button("Cancelar"):
                st.session_state["pagina_recuperacao"] = "solicitar_email"
                st.rerun()
        elif st.session_state["pagina_recuperacao"] == "nova_senha":
            email_rec = st.session_state["email_recuperacao"]
            s1 = st.text_input("Nova Senha", type="password")
            s2 = st.text_input("Repetir Nova Senha", type="password")
            if st.button("ALTERAR SENHA", type="primary"):
                if s1 != s2: st.error("Senhas não coincidem!")
                elif len(s1) < 4: st.error("Senha muito curta!")
                else:
                    usuarios[email_rec]["senha"] = s1
                    salvar_json(ARQUIVO_USUARIOS, usuarios)
                    st.success("Senha alterada! Faça login.")
                    st.session_state["pagina_recuperacao"] = "solicitar_email"
                    st.rerun()
    
    st.markdown("---")
    if st.button("🔑 PAINEL DE ADMINISTRAÇÃO"):
        st.session_state["pagina"] = "Painel de Administração"
        st.rerun()

# ==============================================
# PLANOS
# ==============================================
def tela_planos():
    botao_voltar_menu()
    st.header("Escolha Seu Plano")
    col1, col2, col3 = st.columns(3)
    email = st.session_state["email_usuario"]
    
    with col1:
        st.subheader("Gratuito")
        st.write("**R$ 0,00**")
        st.write("✅ 3 moedas | 2 corretoras")
        st.write("❌ Bot automático")
        if st.button("Escolher Gratuito", type="primary"):
            usuarios[email].update({"plano":"Gratuito","plano_escolhido":"Gratuito","plano_ativo":True,"status_pagamento":"aprovado"})
            salvar_json(ARQUIVO_USUARIOS, usuarios)
            st.success("Plano ativado!")
            st.rerun()
    
    with col2:
        st.subheader("Pro")
        st.write("**R$ 49,90/mês**")
        st.write("✅ 50 moedas | 4 corretoras")
        st.write("✅ Bot + alertas e-mail")
        if st.button("Escolher Pro", type="primary"):
            usuarios[email].update({"plano_escolhido":"Pro","valor_pago":49.90,"status_pagamento":"pendente"})
            salvar_json(ARQUIVO_USUARIOS, usuarios)
            st.session_state["pagina"] = "Pagamento"
            st.rerun()
    
    with col3:
        st.subheader("Premium")
        st.write("**R$ 99,90/mês**")
        st.write("✅ Ilimitado | Todas corretoras")
        st.write("✅ Bot + alertas e-mail/WhatsApp")
        if st.button("Escolher Premium", type="primary"):
            usuarios[email].update({"plano_escolhido":"Premium","valor_pago":99.90,"status_pagamento":"pendente"})
            salvar_json(ARQUIVO_USUARIOS, usuarios)
            st.session_state["pagina"] = "Pagamento"
            st.rerun()

# ==============================================
# PAGAMENTO
# ==============================================
def tela_pagamento():
    botao_voltar_menu()
    email = st.session_state["email_usuario"]
    plano = usuarios[email].get("plano_escolhido", "Pro")
    valor = PLANOS[plano]["preco"]
    st.header("Pagamento via PIX")
    st.info(f"""
    **Dados do PIX:**
    - Recebedor: {CONFIG['pix_nome_recebedor']}
    - Chave: `{CONFIG['pix_chave']}`
    - Valor: R$ {valor:.2f}
    """)
    comprovante = st.file_uploader("Anexar Comprovante", type=["jpg","jpeg","png"])
    if st.button("JÁ PAGUEI — ENVIAR COMPROVANTE", type="primary"):
        id_pag = f"PAG{datetime.now().strftime('%Y%m%d%H%M%S')}"
        caminho = ""
        if comprovante:
            os.makedirs("comprovantes", exist_ok=True)
            caminho = f"comprovantes/{id_pag}_{comprovante.name}"
            with open(caminho, "wb") as f:
                f.write(comprovante.getbuffer())
        usuarios[email].update({"id_pagamento":id_pag,"caminho_comprovante":caminho})
        salvar_json(ARQUIVO_USUARIOS, usuarios)
        texto = f"NOVO PAGAMENTO!\nCliente: {email}\nPlano: {plano}\nValor: R$ {valor:.2f}"
        link = f"https://wa.me/{CONFIG['whatsapp_admin']}?text={quote(texto)}"
        st.success("Enviado! Aguardando aprovação.")
        st.markdown(f"[Avisar no WhatsApp →]({link})")
    if st.button("Voltar"):
        st.session_state["pagina"] = "Planos"
        st.rerun()

# ==============================================
# CONFIGURAR APIS
# ==============================================
def tela_apis():
    botao_voltar_menu()
    email = st.session_state["email_usuario"]
    st.header("🔗 Minhas Corretoras (APIs)")
    corretora = st.selectbox("Corretora", CORRETORAS_DISPONIVEIS)
    chave = st.text_input(f"API Key — {corretora}", type="password")
    segredo = st.text_input(f"API Secret — {corretora}", type="password")
    if st.button("💾 Salvar", type="primary"):
        if not chave or not segredo:
            st.error("Preencha tudo!")
        else:
            if "apis_corretoras" not in usuarios[email]:
                usuarios[email]["apis_corretoras"] = {}
            usuarios[email]["apis_corretoras"][corretora] = {
                "api_key": chave, "api_secret": segredo,
                "salvo_em": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            salvar_json(ARQUIVO_USUARIOS, usuarios)
            st.success(f"✅ {corretora} salva!")
    st.subheader("Conectadas")
    conectadas = usuarios[email].get("apis_corretoras", {})
    if not conectadas:
        st.info("Nenhuma ainda.")
    else:
        for c, d in conectadas.items():
            st.write(f"✅ {c} — Salvo em {d['salvo_em']}")

# ==============================================
# PAINEL ADMIN — COMPLETO: APROVAR / EDITAR / EXCLUIR
# ==============================================
def painel_admin():
    botao_voltar_menu()
    if not st.session_state.get("admin_logado"):
        st.header("🔑 Painel de Administração")
        senha = st.text_input("Senha de Admin", type="password")
        if st.button("ENTRAR", type="primary"):
            if senha == CONFIG["senha_admin"]:
                st.session_state["admin_logado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
        return
    
    st.header("⚙️ PAINEL DE ADMINISTRAÇÃO")
    aba1, aba2, aba3 = st.tabs(["Aprovar Planos", "Gerenciar Usuários", "Configurações"])
    
    with aba1:
        st.subheader("Pagamentos Pendentes")
        usrs = carregar_json(ARQUIVO_USUARIOS, {})
        pendentes = {e:d for e,d in usrs.items() if d.get("status_pagamento")=="pendente"}
        if not pendentes:
            st.info("Nenhum pendente!")
        else:
            for email, d in pendentes.items():
                st.markdown(f"**{d.get('nome_usuario',email)}** — {d.get('plano_escolhido')}")
                st.write(f"ID: {d.get('id_pagamento')}")
                if d.get("caminho_comprovante") and os.path.exists(d["caminho_comprovante"]):
                    st.image(d["caminho_comprovante"], width=300)
                col_ap, col_rej = st.columns(2)
                with col_ap:
                    if st.button(f"✅ APROVAR — {email[:15]}", key=f"apr_{email}"):
                        plano = d.get("plano_escolhido", "Pro")
                        usuarios[email].update({
                            "plano": plano, "plano_ativo": True, "status_pagamento": "aprovado"
                        })
                        salvar_json(ARQUIVO_USUARIOS, usuarios)
                        nome = d.get("nome_usuario", email.split("@")[0])
                        ok, msg = enviar_email_aprovacao_plano(email, nome, plano)
                        if ok:
                            st.success(f"Aprovado! E-mail enviado para {email} ✅")
                        else:
                            st.warning(f"Aprovado, mas e-mail: {msg}")
                        st.rerun()
                with col_rej:
                    if st.button(f"❌ REJEITAR — {email[:15]}", key=f"rej_{email}"):
                        usuarios[email]["status_pagamento"] = "rejeitado"
                        salvar_json(ARQUIVO_USUARIOS, usuarios)
                        st.rerun()
    
    with aba2:
        st.subheader("👥 Gerenciar Usuários")
        usrs = carregar_json(ARQUIVO_USUARIOS, {})
        if not usrs:
            st.info("Nenhum usuário cadastrado.")
        else:
            for email, d in usrs.items():
                with st.expander(f"👤 {d.get('nome_usuario')} | {email} | {d.get('plano')} | {'✅ Ativo' if d.get('plano_ativo') else '⏳ Pendente'}"):
                    with st.form(f"editar_{email}"):
                        novo_plano = st.selectbox(
                            "Alterar Plano",
                            ["Gratuito", "Pro", "Premium"],
                            index=["Gratuito", "Pro", "Premium"].index(d.get("plano", "Gratuito"))
                        )
                        ativo = st.checkbox("Conta Ativa", value=d.get("plano_ativo", False))
                        if st.form_submit_button("💾 Salvar Alterações"):
                            usuarios[email].update({
                                "plano": novo_plano,
                                "plano_escolhido": novo_plano,
                                "plano_ativo": ativo
                            })
                            salvar_json(ARQUIVO_USUARIOS, usuarios)
                            st.success("Alterações salvas! ✅")
                            st.rerun()
                    
                    if st.button(f"🗑️ EXCLUIR USUÁRIO", key=f"del_{email}", type="secondary"):
                        if f"confirmar_excluir_{email}" not in st.session_state:
                            st.session_state[f"confirmar_excluir_{email}"] = True
                            st.warning(f"Clique NOVAMENTE para confirmar exclusão de {email}")
                        else:
                            del usuarios[email]
                            salvar_json(ARQUIVO_USUARIOS, usuarios)
                            if f"confirmar_excluir_{email}" in st.session_state:
                                del st.session_state[f"confirmar_excluir_{email}"]
                            st.success("Usuário excluído! ✅")
                            st.rerun()
    
    with aba3:
        st.subheader("Configurações do Sistema")
        CONFIG["pix_nome_recebedor"] = st.text_input("Nome PIX", CONFIG["pix_nome_recebedor"])
        CONFIG["pix_chave"] = st.text_input("Chave PIX", CONFIG["pix_chave"])
        CONFIG["whatsapp_admin"] = st.text_input("WhatsApp Admin (só números)", CONFIG["whatsapp_admin"])
        CONFIG["email_remetente"] = st.text_input("E-mail de Envio", CONFIG["email_remetente"])
        CONFIG["senha_app_email"] = st.text_input("Senha do App de E-mail", CONFIG["senha_app_email"], type="password")
        CONFIG["senha_admin"] = st.text_input("Senha de Admin", CONFIG["senha_admin"], type="password")
        if st.button("💾 Salvar Configurações", type="primary"):
            salvar_json(ARQUIVO_SISTEMA, CONFIG)
            st.success("Salvo! ✅")

# ==============================================
# PAINEL PRINCIPAL DO USUÁRIO
# ==============================================
def painel_usuario():
    email = st.session_state["email_usuario"]
    dados = usuarios[email]
    plano = dados.get("plano", "Gratuito")
    p = PLANOS[plano]
    saldos = obter_saldos_usuario(email)
    
    st.sidebar.markdown(f"**👤 {dados.get('nome_usuario', email.split('@')[0])}**")
    st.sidebar.write(f"Plano: {plano}")
    pag = st.sidebar.radio("Menu", [
        "Início", "Saldo das Corretoras", "Scanner", "Minhas Corretoras",
        "Histórico de Operações", "Calculadora", "Alterar Plano"
    ])
    botao_sair_conta()
    
    if pag == "Início":
        st.header("Bem-vindo(a) ao Arbitragem AI 🚀")
        st.success(f"✅ Plano {plano} ativo!")
        c1, c2, c3 = st.columns(3)
        c1.metric("Corretoras", len(p["corretoras"]))
        c2.metric("Moedas", p["moedas"] if p["moedas"]<100 else "Ilimitadas")
        c3.metric("Bot", "✅ Simulação" if p["bot_operacional"] else "❌ Indisponível")
        st.info("⚠️ O bot opera em MODO SIMULADO — valores são apenas demonstração, sem transações reais.")
    
    elif pag == "Saldo das Corretoras":
        st.header("💰 Saldo e Evolução por Corretora")
        st.info("Valores atualizados após cada operação executada")
        
        conectadas = list(dados.get("apis_corretoras", {}).keys())
        corretoras_exibir = conectadas if conectadas else p["corretoras"]
        
        for corretora in corretoras_exibir:
            s = saldos.get(corretora, {})
            inicial = s.get("saldo_inicial", 1000.0)
            atual = s.get("saldo_atual", 1000.0)
            lucro = s.get("lucro_total", 0.0)
            qtd = s.get("qtd_operacoes", 0)
            evolucao = ((atual - inicial) / inicial * 100) if inicial > 0 else 0
            
            with st.expander(f"📊 {corretora} — R$ {atual:.2f}"):
                col1, col2 = st.columns(2)
                col1.metric("Saldo Inicial", f"R$ {inicial:.2f}")
                col2.metric("Saldo Atual", f"R$ {atual:.2f}", f"{evolucao:+.2f}%")
                col1.metric("Lucro Total", f"R$ {lucro:.2f}", "+" if lucro >= 0 else "")
                col2.metric("Operações Executadas", qtd)
                st.write(f"Última atualização: {s.get('ultima_atualizacao', '—')}")
    
    elif pag == "Alterar Plano":
        tela_planos()
    
    elif pag == "Minhas Corretoras":
        tela_apis()
    
    elif pag == "Calculadora":
        st.header("🧮 Calculadora de Lucro")
        c1, c2 = st.columns(2)
        with c1:
            pc = st.number_input("Preço Compra", 0.0, 100000.0, 100.0)
            pv = st.number_input("Preço Venda", 0.0, 100000.0, 102.0)
            taxa = st.number_input("Taxa (%)", 0.0, 5.0, 0.1)
            valor_inv = st.number_input("Valor a Investir (R$)", 10.0, 10000.0, 100.0)
        with c2:
            calc = calcular_lucro_liquido(pc, pv, taxa)
            lucro_valor = valor_inv * (calc['lucro_liquido_perc'] / 100)
            st.metric("Lucro Líquido %", f"{calc['lucro_liquido_perc']:.2f}%")
            st.metric("Lucro Líquido R$", f"R$ {lucro_valor:.2f}")
            if calc['lucro_liquido_perc'] <= 0:
                st.error("❌ Não dá lucro após taxas!")
    
    elif pag == "Histórico de Operações":
        st.header("📊 Histórico de Operações")
        hist = carregar_json(ARQUIVO_HISTORICO_OPERACOES, [])
        minhas = [x for x in hist if x.get("email")==email]
        
        if not minhas:
            st.info("Nenhuma operação executada ainda. Faça uma operação no Scanner para ver a evolução do saldo!")
        else:
            lucro_total = sum(op.get("lucro_valor", 0) for op in minhas if op.get("status")=="executada")
            qtd_sucesso = sum(1 for op in minhas if op.get("status")=="executada")
            qtd_total = len(minhas)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Operações", f"{qtd_sucesso}/{qtd_total}")
            c2.metric("Lucro Total Acumulado", f"R$ {lucro_total:.2f}", "+" if lucro_total >= 0 else "")
            saldo_atual_geral = sum(s.get("saldo_atual", 0) for s in saldos.values())
            c3.metric("Saldo Total Geral", f"R$ {saldo_atual_geral:.2f}")
            
            st.markdown("---")
            for op in minhas[:50]:
                status_icon = {"executada": "✅", "simulada": "🔵", "falhou": "❌"}.get(op.get("status", ""), "—")
                cor_compra = op.get("comprar_em", "")
                cor_venda = op.get("vender_em", "")
                lucro_val = op.get("lucro_valor", 0)
                valor_inv = op.get("valor_investido", 0)
                
                with st.expander(f"{status_icon} {op.get('hora')} | {op.get('moeda')} | {op.get('lucro_perc', 0):.2f}% | R$ {lucro_val:.2f}"):
                    st.write(f"De: {cor_compra} → Para: {cor_venda}")
                    st.write(f"Valor Investido: R$ {valor_inv:.2f}")
                    st.write(f"Lucro Obtido: R$ {lucro_val:.2f}")
                    st.write(f"Modo: {op.get('modo', 'manual').upper()}")
                    st.write(f"Status: {op.get('status', '—').upper()}")
    
    elif pag == "Scanner":
        st.header("🔍 Scanner de Arbitragem")
        
        if p["bot_operacional"]:
            bot_ativo = st.checkbox("🤖 ATIVAR BOT AUTOMÁTICO (SIMULAÇÃO)", value=st.session_state["bot_ativo"])
            if bot_ativo != st.session_state["bot_ativo"]:
                st.session_state["bot_ativo"] = bot_ativo
                st.rerun()
        else:
            st.info("🔒 Faça upgrade para Pro/Premium usar o Bot")
        
        min_lucro = st.slider("Lucro Mínimo (%)", 0.1, 5.0, 0.5, 0.1)
        valor_padrao = st.number_input("Valor Padrão por Operação (R$)", 10.0, 1000.0, 100.0)
        
        conectadas = list(dados.get("apis_corretoras", {}).keys())
        corretoras = conectadas if conectadas else p["corretoras"]
        moedas = MOEDAS_MONITORADAS[:p["moedas"]] if p["moedas"]<100 else MOEDAS_MONITORADAS
        
        if st.button("🔄 ESCANEAR AGORA", type="primary") or st.session_state["bot_ativo"]:
            with st.spinner("Analisando preços..."):
                ops = escanear_oportunidades(corretoras, moedas, min_lucro)
            
            if st.session_state["bot_ativo"] and ops and p["bot_operacional"]:
                agora = datetime.now()
                ultima = st.session_state["ultima_execucao_bot"]
                if not ultima or (agora - ultima).total_seconds() > p["atualizacao_segundos"]:
                    st.session_state["ultima_execucao_bot"] = agora
                    melhor = ops[0]
                    ok, _ = verificar_chaves_corretoras(email, melhor["comprar_em"], melhor["vender_em"])
                    if ok:
                        st.info(f"🤖 BOT: Executando {melhor['moeda']}...")
                        exec_ok, msg = executar_operacao(melhor, email, valor_padrao)
                        if exec_ok:
                            st.success(msg)
                        else:
                            st.warning(msg)
                        time.sleep(2)
                        st.rerun()
            
            if not ops:
                st.info("Nenhuma oportunidade agora.")
            else:
                st.subheader(f"✅ {len(ops)} oportunidade(s) encontrada(s)")
                st.warning("⚠️ Simulação — confirme sempre os preços na corretora!")
                for i, op in enumerate(ops[:10]):
                    with st.expander(f"💰 {op['moeda']} — {op['lucro_liquido_perc']:.2f}% LÍQUIDO"):
                        st.write(f"Comprar: {op['comprar_em']} — ${op['preco_compra']:.4f}")
                        st.write(f"Vender: {op['vender_em']} — ${op['preco_venda']:.4f}")
                        st.write(f"Lucro: {op['lucro_liquido_perc']:.2f}%")
                        lucro_estimado = valor_padrao * (op['lucro_liquido_perc'] / 100)
                        st.write(f"Retorno estimado: R$ {lucro_estimado:.2f}")
                        
                        ok, _ = verificar_chaves_corretoras(email, op["comprar_em"], op["vender_em"])
                        if ok:
                            if st.button(f"⚡ EXECUTAR SIMULAÇÃO — {op['moeda']}", key=f"ex{i}", type="primary"):
                                exec_ok, msg_exec = executar_operacao(op, email, valor_padrao)
                                if exec_ok:
                                    st.success(msg_exec)
                                    st.rerun()
                                else:
                                    st.error(msg_exec)
                        else:
                            st.info(msg)
                            st.warning("Configure as chaves das DUAS corretoras para executar!")

# ==============================================
# ROTEAMENTO PRINCIPAL
# ==============================================
if "pagina" not in st.session_state:
    st.session_state["pagina"] = "inicio"

pagina = st.session_state["pagina"]

if pagina == "Painel de Administração":
    painel_admin()
elif st.session_state["logado"]:
    if pagina == "Planos":
        tela_planos()
    elif pagina == "Pagamento":
        tela_pagamento()
    else:
        painel_usuario()
else:
    tela_login()
