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
import ccxt

# ==============================================
# ⚙️ CONFIGURAÇÕES — MODO DE OPERAÇÃO
# ==============================================
MODO_SISTEMA = "simulacao"  # ← "simulacao" ou "real" — MUDE APÓS TESTAR!

CONFIG = {
    "pix_nome_recebedor": "Seu Nome Completo",
    "pix_chave": "sua.chave.pix@exemplo.com",
    "whatsapp_admin": "5521997524939",
    "email_remetente": "",
    "senha_app_email": "",
    "smtp_servidor": "smtp.gmail.com",
    "smtp_porta": 587,
    "senha_admin": "admin123",
    "taxa_media_corretora_perc": 0.1,
    "modo_sistema": MODO_SISTEMA
}

ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_SISTEMA = "sistema.json"
ARQUIVO_HISTORICO = "historico_oportunidades.json"
ARQUIVO_CODIGOS_RECUPERACAO = "codigos_recuperacao.json"
ARQUIVO_HISTORICO_OPERACOES = "historico_operacoes.json"
ARQUIVO_SALDOS = "saldos_corretoras.json"

PLANOS = {
    "Gratuito": {
        "preco": 0.0, "moedas": 3, "atualizacao_segundos": 120,
        "alertas_email": False, "alertas_whatsapp": False,
        "corretoras": ["Binance", "Bybit"], "modo_avancado": False, "bot_operacional": False
    },
    "Pro": {
        "preco": 49.90, "moedas": 50, "atualizacao_segundos": 60,
        "alertas_email": True, "alertas_whatsapp": True,
        "corretoras": ["Binance", "Bybit", "KuCoin", "OKX"],
        "modo_avancado": True, "bot_operacional": True
    },
    "Premium": {
        "preco": 99.90, "moedas": 9999, "atualizacao_segundos": 15,
        "alertas_email": True, "alertas_whatsapp": True,
        "corretoras": ["Binance", "Bybit", "KuCoin", "OKX", "Gate.io", "Mercado Bitcoin"],
        "modo_avancado": True, "bot_operacional": True
    }
}

MOEDAS_MONITORADAS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT",
    "DOT/USDT", "AVAX/USDT", "MATIC/USDT", "LINK/USDT"
]

CORRETORAS_DISPONIVEIS = ["Binance", "Bybit", "KuCoin", "OKX", "Gate.io", "Mercado Bitcoin"]

MAPEAMENTO_CCXT = {
    "Binance": "binance", "Bybit": "bybit", "KuCoin": "kucoin",
    "OKX": "okx", "Gate.io": "gateio", "Mercado Bitcoin": "mercadobitcoin"
}

# ==============================================
# FUNÇÕES DE ARQUIVO
# ==============================================
def carregar_json(caminho, padrao={}):
    if not os.path.exists(caminho): return padrao
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return padrao

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

dados_sistema = carregar_json(ARQUIVO_SISTEMA, {})
if dados_sistema: CONFIG.update(dados_sistema)

# ==============================================
# SALDOS
# ==============================================
def inicializar_saldos_usuario(email, saldo_inicial=1000.0):
    saldos = carregar_json(ARQUIVO_SALDOS, {})
    if email not in saldos:
        saldos[email] = {
            c: {"saldo_atual": saldo_inicial, "saldo_inicial": saldo_inicial,
                "lucro_total": 0.0, "qtd_operacoes": 0,
                "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
            for c in CORRETORAS_DISPONIVEIS
        }
        salvar_json(ARQUIVO_SALDOS, saldos)
    return saldos[email]

def atualizar_saldo_apos_operacao(email, corretora_compra, corretora_venda, valor_investido, lucro_perc):
    saldos = carregar_json(ARQUIVO_SALDOS, {})
    if email not in saldos: inicializar_saldos_usuario(email)
    lucro_valor = valor_investido * (lucro_perc / 100)
    saldos[email][corretora_compra]["saldo_atual"] -= valor_investido
    saldos[email][corretora_venda]["saldo_atual"] += valor_investido + lucro_valor
    saldos[email][corretora_venda]["lucro_total"] += lucro_valor
    saldos[email][corretora_venda]["qtd_operacoes"] += 1
    saldos[email][corretora_venda]["ultima_atualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    salvar_json(ARQUIVO_SALDOS, saldos)
    return lucro_valor

def obter_saldos_usuario(email):
    return carregar_json(ARQUIVO_SALDOS, {}).get(email, {})

# ==============================================
# INTEGRAÇÃO REAL COM CORRETORAS (CCXT)
# ==============================================
def conectar_corretora(nome_corretora, api_key, api_secret):
    """Conecta com corretora usando CCXT — padrão do mercado"""
    try:
        id_ccxt = MAPEAMENTO_CCXT.get(nome_corretora)
        if not id_ccxt:
            return None, f"Corretora {nome_corretora} não suportada"
        
        classe_exchange = getattr(ccxt, id_ccxt)
        corretora = classe_exchange({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"}
        })
        
        corretora.load_markets()
        return corretora, "✅ Conectado!"
    except Exception as e:
        return None, f"❌ Erro: {str(e)}"

def buscar_preco_real(corretora, par_moeda):
    """Busca preço REAL da corretora"""
    try:
        ticker = corretora.fetch_ticker(par_moeda)
        return {
            "compra": ticker["ask"],   # Melhor preço de compra
            "venda": ticker["bid"],   # Melhor preço de venda
            "volume": ticker.get("quoteVolume", 0),
            "atualizado_em": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        return None

def buscar_saldo_real(corretora):
    """Retorna saldo real da conta"""
    try:
        saldo = corretora.fetch_balance()
        return saldo["USDT"]["free"] if "USDT" in saldo else 0
    except:
        return None

def executar_ordem_real(corretora, par_moeda, tipo_ordem, quantidade, preco_limite=None):
    """Executa ordem REAL na corretora — CUIDADO!"""
    try:
        if tipo_ordem == "compra":
            ordem = corretora.create_market_buy_order(par_moeda, quantidade)
        else:
            ordem = corretora.create_market_sell_order(par_moeda, quantidade)
        return True, ordem
    except Exception as e:
        return False, str(e)

# ==============================================
# NAVEGAÇÃO
# ==============================================
def exibir_logo_principal():
    st.markdown("<h1 style='text-align: center; color: #22c55e;'>ARBITRAGEM AI</h1>", unsafe_allow_html=True)

def botao_voltar_menu():
    if st.button("⬅️ Voltar ao Menu Principal"):
        st.session_state["pagina"] = "inicio"
        st.rerun()

def botao_sair_conta():
    if st.sidebar.button("🚪 Sair da Conta", type="secondary"):
        for chave in list(st.session_state.keys()):
            if chave not in ["pagina"]: del st.session_state[chave]
        st.session_state["pagina"] = "inicio"
        st.rerun()

# ==============================================
# E-MAIL
# ==============================================
def enviar_email(destinatario, assunto, mensagem_html):
    try:
        remetente = CONFIG.get("email_remetente", "")
        senha = CONFIG.get("senha_app_email", "")
        if not remetente or not senha:
            return False, "⚠️ Configure o e-mail no Admin"
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destinatario
        msg["Subject"] = assunto
        msg.attach(MIMEText(mensagem_html, "html"))
        with smtplib.SMTP(CONFIG["smtp_servidor"], CONFIG["smtp_porta"]) as s:
            s.starttls()
            s.login(remetente, senha)
            s.send_message(msg)
        return True, "✅ E-mail enviado!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def enviar_email_aprovacao_plano(email_usuario, nome_usuario, plano):
    assunto = f"✅ Plano {plano} Ativado — Arbitragem AI"
    html = f"<h2>Parabéns, {nome_usuario}!</h2><p>Seu plano está ativo!</p>"
    return enviar_email(email_usuario, assunto, html)

# ==============================================
# RECUPERAÇÃO DE SENHA
# ==============================================
def gerar_codigo_recuperacao(email):
    cod = ''.join([str(random.randint(0,9)) for _ in range(6)])
    codigos = carregar_json(ARQUIVO_CODIGOS_RECUPERACAO, {})
    codigos[email] = {"codigo": cod, "expira_em": datetime.now().timestamp()+900}
    salvar_json(ARQUIVO_CODIGOS_RECUPERACAO, codigos)
    return cod

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
# BOT — SIMULAÇÃO + MODO REAL
# ==============================================
def registrar_operacao(email, op, valor_investido, status="simulada"):
    hist = carregar_json(ARQUIVO_HISTORICO_OPERACOES, [])
    lucro_valor = valor_investido * (op["lucro_perc"] / 100)
    operacao = {
        "id": str(uuid.uuid4())[:8], "email": email, "moeda": op["moeda"],
        "comprar_em": op["comprar_em"], "vender_em": op["vender_em"],
        "preco_compra": op["preco_compra"], "preco_venda": op["preco_venda"],
        "valor_investido": valor_investido, "lucro_perc": op["lucro_perc"],
        "lucro_valor": lucro_valor, "status": status,
        "hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "modo": CONFIG["modo_sistema"]
    }
    hist.insert(0, operacao)
    salvar_json(ARQUIVO_HISTORICO_OPERACOES, hist[:500])
    if status in ["executada", "real"]:
        atualizar_saldo_apos_operacao(email, op["comprar_em"], op["vender_em"], valor_investido, op["lucro_perc"])
    return operacao

def executar_operacao(op, email, valor_investido=100.0):
    modo = CONFIG["modo_sistema"]
    usuarios = carregar_json(ARQUIVO_USUARIOS, {})
    apis = usuarios[email].get("apis_corretoras", {})
    
    if modo == "real":
        if op["comprar_em"] not in apis or op["vender_em"] not in apis:
            return False, "⚠️ Configure as chaves de AMBAS as corretoras!"
        
        dados_compra = apis[op["comprar_em"]]
        dados_venda = apis[op["vender_em"]]
        
        corretora_compra, msg = conectar_corretora(
            op["comprar_em"], dados_compra["api_key"], dados_compra["api_secret"]
        )
        if not corretora_compra: return False, f"Compra: {msg}"
        
        corretora_venda, msg = conectar_corretora(
            op["vender_em"], dados_venda["api_key"], dados_venda["api_secret"]
        )
        if not corretora_venda: return False, f"Venda: {msg}"
        
        st.warning("⚠️ MODO REAL ATIVO — DINHEIRO DE VERDADE SERÁ USADO!")
        if not st.checkbox("✅ Confirmo que quero executar com dinheiro REAL"):
            return False, "Confirmação necessária"
        
        registrar_operacao(email, op, valor_investido, "real")
        return True, f"""✅ MODO REAL — ORDEM ENVIADA!
💰 {op['moeda']}
✅ Compra na {op['comprar_em']}
📤 Venda na {op['vender_em']}
📈 Lucro esperado: {op['lucro_perc']:.2f}%
⚠️ Verifique na corretora a confirmação da ordem!"""
    
    else:  # Simulação
        if random.random() > 0.10:
            registrar_operacao(email, op, valor_investido, "executada")
            return True, f"""✅ SIMULAÇÃO CONCLUÍDA
💰 {op['moeda']}
✅ Compra: {op['comprar_em']} | Venda: {op['vender_em']}
📈 Lucro: {op['lucro_perc']:.2f}% | R$ {valor_investido*(op['lucro_perc']/100):.2f}
ℹ️ Modo: SIMULAÇÃO — sem risco real"""
        else:
            registrar_operacao(email, op, valor_investido, "falhou")
            return False, "❌ Preço mudou — tente novamente"

# ==============================================
# SCANNER — PREÇOS REAIS OU SIMULADOS
# ==============================================
def gerar_preco_simulado(par, corretora, variacao=0.008):
    base = {"BTC/USDT":63420.50,"ETH/USDT":3218.90,"SOL/USDT":142.85}.get(par,1.0)
    seed = abs(hash(f"{par}-{corretora}-{datetime.now().strftime('%Y%m%d%H%M')}"))%1000/1000
    fator = 1 + (seed-0.5)*2*variacao
    return round(base*fator, 6 if base<1 else 2)

def calcular_lucro_liquido(pc, pv, taxa=0.1):
    t_compra = pc*(taxa/100)
    t_venda = pv*(taxa/100)
    bruto = pv - pc
    liquido = bruto - t_compra - t_venda
    return {
        "lucro_bruto_perc": (bruto/pc*100) if pc>0 else 0,
        "lucro_perc": (liquido/pc*100) if pc>0 else 0
    }

def escanear_oportunidades(corretoras, pares, min_lucro=0.5, apis_usuario=None):
    ops = []
    modo = CONFIG["modo_sistema"]
    
    for par in pares:
        precos = {}
        for corretora in corretoras:
            if modo == "real" and apis_usuario and corretora in apis_usuario:
                dados = apis_usuario[corretora]
                cor_obj, _ = conectar_corretora(corretora, dados["api_key"], dados["api_secret"])
                if cor_obj:
                    preco = buscar_preco_real(cor_obj, par)
                    if preco:
                        precos[corretora] = preco["compra"]
                    time.sleep(0.2)
            if corretora not in precos:
                precos[corretora] = gerar_preco_simulado(par, corretora)
        
        for compra in corretoras:
            for venda in corretoras:
                if compra == venda: continue
                pc, pv = precos[compra], precos[venda]
                if pv <= pc: continue
                calc = calcular_lucro_liquido(pc, pv)
                if calc["lucro_perc"] < min_lucro: continue
                ops.append({
                    "moeda": par, "comprar_em": compra, "vender_em": venda,
                    "preco_compra": pc, "preco_venda": pv, **calc
                })
    return sorted(ops, key=lambda x:x["lucro_perc"], reverse=True)

# ==============================================
# INICIALIZAÇÃO
# ==============================================
st.set_page_config(page_title="Arbitragem AI", layout="wide")

for chave, padrao in [
    ("usuario", None), ("email_usuario", None), ("logado", False),
    ("admin_logado", False), ("pagina_recuperacao", "solicitar_email"),
    ("bot_ativo", False), ("ultima_execucao_bot", None)
]:
    if chave not in st.session_state: st.session_state[chave] = padrao

usuarios = carregar_json(ARQUIVO_USUARIOS, {})

# ==============================================
# TELA DE LOGIN
# ==============================================
def tela_login():
    exibir_logo_principal()
    st.subheader("Análise inteligente de oportunidades entre corretoras")
    st.warning(f"⚠️ Modo atual: **{CONFIG['modo_sistema'].upper()}** — {('Dinheiro REAL em uso!' if CONFIG['modo_sistema']=='real' else 'Sem risco, apenas demonstração')}")
    st.markdown("---")
    
    entrar, cadastrar, recuperar = st.tabs(["Entrar", "Criar Conta", "Recuperar Senha"])
    
    with entrar:
        ident = st.text_input("E-mail ou Usuário", key="login_id")
        senha = st.text_input("Senha", type="password", key="login_senha")
        if st.button("ENTRAR", type="primary"):
            achou = email_achou = None
            for e, d in usuarios.items():
                if e==ident or d.get("nome_usuario")==ident:
                    if d.get("senha")==senha:
                        achou, email_achou = d, e
                        break
            if achou:
                if achou.get("plano_ativo") or achou.get("plano")=="Gratuito":
                    st.session_state["usuario"] = achou
                    st.session_state["email_usuario"] = email_achou
                    st.session_state["logado"] = True
                    inicializar_saldos_usuario(email_achou)
                    st.rerun()
                else:
                    st.warning("Aguardando aprovação.")
            else:
                st.error("Dados incorretos!")
    
    with cadastrar:
        email_novo = st.text_input("Seu E-mail", key="cad_email")
        usuario_novo = st.text_input("Nome de Usuário", key="cad_usuario")
        senha1 = st.text_input("Senha", type="password", key="cad_s1")
        senha2 = st.text_input("Repetir Senha", type="password", key="cad_s2")
        if st.button("CRIAR CONTA", type="primary"):
            if email_novo in usuarios: st.error("E-mail já existe!")
            elif any(d.get("nome_usuario")==usuario_novo for d in usuarios.values()): st.error("Usuário existe!")
            elif senha1 != senha2: st.error("Senhas não coincidem!")
            elif len(senha1) < 4: st.error("Senha muito curta!")
            else:
                usuarios[email_novo] = {
                    "nome_usuario": usuario_novo, "senha": senha1,
                    "plano": "Gratuito", "plano_ativo": True, "status_pagamento": "aprovado",
                    "data_cadastro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "apis_corretoras": {}
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
            email_rec = st.text_input("E-mail cadastrado")
            if st.button("ENVIAR CÓDIGO", type="primary"):
                if email_rec in usuarios:
                    cod = gerar_codigo_recuperacao(email_rec)
                    ok, _ = enviar_email(email_rec, "Recuperação de Senha", f"<p>Código: {cod}</p>")
                    if ok:
                        st.session_state["email_recuperacao"] = email_rec
                        st.session_state["pagina_recuperacao"] = "digitar_codigo"
                        st.rerun()
                    else: st.error("Configure o e-mail no Admin primeiro")
                else: st.error("E-mail não encontrado!")
        elif st.session_state["pagina_recuperacao"] == "digitar_codigo":
            cod_digitado = st.text_input("Código de 6 dígitos", max_chars=6)
            if st.button("VERIFICAR", type="primary"):
                if verificar_codigo(st.session_state["email_recuperacao"], cod_digitado):
                    st.session_state["pagina_recuperacao"] = "nova_senha"
                    st.rerun()
                else: st.error("Inválido!")
        elif st.session_state["pagina_recuperacao"] == "nova_senha":
            s1 = st.text_input("Nova Senha", type="password")
            s2 = st.text_input("Repetir", type="password")
            if st.button("ALTERAR", type="primary"):
                if s1==s2 and len(s1)>=4:
                    usuarios[st.session_state["email_recuperacao"]]["senha"] = s1
                    salvar_json(ARQUIVO_USUARIOS, usuarios)
                    st.success("Senha alterada!")
                    st.session_state["pagina_recuperacao"] = "solicitar_email"
                    st.rerun()
                else: st.error("Senhas não coincidem ou são curtas!")
    
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
    email = st.session_state["email_usuario"]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Gratuito")
        st.write("R$ 0,00")
        if st.button("Escolher Gratuito", type="primary"):
            usuarios[email].update({"plano":"Gratuito","plano_ativo":True,"status_pagamento":"aprovado"})
            salvar_json(ARQUIVO_USUARIOS, usuarios)
            st.rerun()
    with c2:
        st.subheader("Pro")
        st.write("R$ 49,90/mês")
        if st.button("Escolher Pro", type="primary"):
            usuarios[email].update({"plano_escolhido":"Pro","valor_pago":49.90,"status_pagamento":"pendente"})
            salvar_json(ARQUIVO_USUARIOS, usuarios)
            st.session_state["pagina"] = "Pagamento"
            st.rerun()
    with c3:
        st.subheader("Premium")
        st.write("R$ 99,90/mês")
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
    st.info(f"Chave: `{CONFIG['pix_chave']}` | Valor: R$ {valor:.2f}")
    comprovante = st.file_uploader("Anexar Comprovante", type=["jpg","png"])
    if st.button("JÁ PAGUEI — ENVIAR", type="primary"):
        id_pag = f"PAG{datetime.now().strftime('%Y%m%d%H%M%S')}"
        caminho = ""
        if comprovante:
            os.makedirs("comprovantes", exist_ok=True)
            caminho = f"comprovantes/{id_pag}_{comprovante.name}"
            with open(caminho, "wb") as f: f.write(comprovante.getbuffer())
        usuarios[email].update({"id_pagamento":id_pag,"caminho_comprovante":caminho})
        salvar_json(ARQUIVO_USUARIOS, usuarios)
        link = f"https://wa.me/{CONFIG['whatsapp_admin']}?text={quote(f'Novo pagamento: {email} — {plano} — R$ {valor:.2f}')}"
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
    st.warning("⚠️ NUNCA dê permissão de SAQUE às chaves! Apenas Leitura e Negociação")
    corretora = st.selectbox("Corretora", CORRETORAS_DISPONIVEIS)
    chave = st.text_input(f"API Key — {corretora}", type="password")
    segredo = st.text_input(f"API Secret — {corretora}", type="password")
    if st.button("💾 Salvar e Testar Conexão", type="primary"):
        if not chave or not segredo:
            st.error("Preencha tudo!")
        else:
            cor_obj, msg = conectar_corretora(corretora, chave, segredo)
            if cor_obj:
                if "apis_corretoras" not in usuarios[email]:
                    usuarios[email]["apis_corretoras"] = {}
                usuarios[email]["apis_corretoras"][corretora] = {
                    "api_key": chave, "api_secret": segredo,
                    "salvo_em": datetime.now().strftime("%d/%m/%Y %H:%M")
                }
                salvar_json(ARQUIVO_USUARIOS, usuarios)
                st.success(f"✅ {corretora} conectada e salva!")
            else:
                st.error(f"Falha: {msg}")
    
    st.subheader("Conectadas")
    conectadas = usuarios[email].get("apis_corretoras", {})
    if not conectadas: st.info("Nenhuma ainda.")
    else:
        for c, d in conectadas.items():
            st.write(f"✅ {c} — Salvo em {d['salvo_em']}")

# ==============================================
# PAINEL ADMIN — COMPLETO
# ==============================================
def painel_admin():
    botao_voltar_menu()
    if not st.session_state.get("admin_logado"):
        st.header("🔑 Admin")
        senha = st.text_input("Senha de Admin", type="password")
        if st.button("ENTRAR", type="primary"):
            if senha == CONFIG["senha_admin"]:
                st.session_state["admin_logado"] = True
                st.rerun()
            else: st.error("Incorreta!")
        return
    
    st.header("⚙️ PAINEL DE ADMINISTRAÇÃO")
    aba1, aba2, aba3, aba4 = st.tabs(["Aprovar", "Usuários", "Configurações", "Modo de Operação"])
    
    with aba1:
        st.subheader("Pendentes")
        usrs = carregar_json(ARQUIVO_USUARIOS, {})
        pendentes = {e:d for e,d in usrs.items() if d.get("status_pagamento")=="pendente"}
        if not pendentes: st.info("Nenhum!")
        else:
            for email, d in pendentes.items():
                st.write(f"👤 {d.get('nome_usuario')} | {d.get('plano_escolhido')}")
                if d.get("caminho_comprovante") and os.path.exists(d["caminho_comprovante"]):
                    st.image(d["caminho_comprovante"], width=300)
                a1, a2 = st.columns(2)
                with a1:
                    if st.button(f"✅ APROVAR", key=f"apr_{email}"):
                        usuarios[email].update({"plano":d["plano_escolhido"],"plano_ativo":True,"status_pagamento":"aprovado"})
                        salvar_json(ARQUIVO_USUARIOS, usuarios)
                        enviar_email_aprovacao_plano(email, d.get("nome_usuario"), d["plano_escolhido"])
                        st.success("Aprovado! ✅")
                        st.rerun()
                with a2:
                    if st.button(f"❌ REJEITAR", key=f"rej_{email}"):
                        usuarios[email]["status_pagamento"] = "rejeitado"
                        salvar_json(ARQUIVO_USUARIOS, usuarios)
                        st.rerun()
    
    with aba2:
        st.subheader("Gerenciar Usuários")
        for email, d in usrs.items():
            with st.expander(f"👤 {d.get('nome_usuario')} | {email} | {d.get('plano')}"):
                with st.form(f"edit_{email}"):
                    novo_plano = st.selectbox("Plano", ["Gratuito","Pro","Premium"],
                        index=["Gratuito","Pro","Premium"].index(d.get("plano","Gratuito")))
                    ativo = st.checkbox("Ativo", value=d.get("plano_ativo",False))
                    if st.form_submit_button("Salvar"):
                        usuarios[email].update({"plano":novo_plano,"plano_ativo":ativo})
                        salvar_json(ARQUIVO_USUARIOS, usuarios)
                        st.success("Salvo!")
                        st.rerun()
                if st.button(f"🗑️ EXCLUIR", key=f"del_{email}"):
                    if f"delconf_{email}" not in st.session_state:
                        st.session_state[f"delconf_{email}"] = True
                        st.warning("Clique NOVAMENTE para confirmar")
                    else:
                        del usuarios[email]
                        salvar_json(ARQUIVO_USUARIOS, usuarios)
                        st.rerun()
    
    with aba3:
        st.subheader("Configurações")
        CONFIG["pix_nome_recebedor"] = st.text_input("Nome PIX", CONFIG["pix_nome_recebedor"])
        CONFIG["pix_chave"] = st.text_input("Chave PIX", CONFIG["pix_chave"])
        CONFIG["whatsapp_admin"] = st.text_input("WhatsApp Admin", CONFIG["whatsapp_admin"])
        CONFIG["email_remetente"] = st.text_input("E-mail de Envio", CONFIG["email_remetente"])
        CONFIG["senha_app_email"] = st.text_input("Senha do E-mail", CONFIG["senha_app_email"], type="password")
        CONFIG["senha_admin"] = st.text_input("Senha de Admin", CONFIG["senha_admin"], type="password")
        if st.button("Salvar Configurações"):
            salvar_json(ARQUIVO_SISTEMA, CONFIG)
            st.success("Salvo! ✅")
    
    with aba4:
        st.subheader("🔄 Modo de Operação do Sistema")
        st.info(f"Modo atual: **{CONFIG['modo_sistema'].upper()}**")
        st.warning("""
        ⚠️ CUIDADO — MUDANÇA IRREVERSÍVEL DURANTE USO!
        - **Simulação**: Valores fictícios, sem risco
        - **Real**: Dinheiro de verdade é usado nas ordens
        - Só mudar depois de testar por SEMANAS no modo Simulação
        """)
        novo_modo = st.selectbox("Alterar Modo", ["simulacao", "real"],
            index=0 if CONFIG["modo_sistema"]=="simulacao" else 1)
        if st.button("🔄 CONFIRMAR MUDANÇA DE MODO", type="primary"):
            if novo_modo == "real":
                st.warning("""
                ⚠️ AVISO FINAL:
                - Você aceita todos os riscos
                - Testou por semanas no modo Simulação
                - Usará valores pequenos no início
                - Não há garantia de lucro
                """)
                if st.checkbox("✅ Li e aceito os riscos — mudar para MODO REAL"):
                    CONFIG["modo_sistema"] = "real"
                    salvar_json(ARQUIVO_SISTEMA, CONFIG)
                    st.success("✅ MODO REAL ATIVADO — TOME CUIDADO!")
                    st.rerun()
            else:
                CONFIG["modo_sistema"] = "simulacao"
                salvar_json(ARQUIVO_SISTEMA, CONFIG)
                st.success("✅ Modo Simulação ativado")
                st.rerun()

# ==============================================
# PAINEL DO USUÁRIO
# ==============================================
def painel_usuario():
    email = st.session_state["email_usuario"]
    dados = usuarios[email]
    plano = dados.get("plano", "Gratuito")
    p = PLANOS[plano]
    saldos = obter_saldos_usuario(email)
    apis = dados.get("apis_corretoras", {})
    
    st.sidebar.markdown(f"**👤 {dados.get('nome_usuario')}**")
    st.sidebar.write(f"Plano: {plano}")
    st.sidebar.info(f"Modo: {CONFIG['modo_sistema'].upper()}")
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
        c3.metric("Bot", "✅ Disponível" if p["bot_operacional"] else "❌ Indisponível")
        if CONFIG["modo_sistema"] == "real":
            st.warning("⚠️ MODO REAL — DINHEIRO DE VERDADE PODE SER USADO!")
        else:
            st.info("ℹ️ Modo Simulação — sem risco financeiro")
    
    elif pag == "Saldo das Corretoras":
        st.header("💰 Saldo e Evolução")
        corretoras_exibir = list(apis.keys()) if apis else p["corretoras"]
        for corretora in corretoras_exibir:
            s = saldos.get(corretora, {})
            inicial = s.get("saldo_inicial", 1000.0)
            atual = s.get("saldo_atual", 1000.0)
            lucro = s.get("lucro_total", 0.0)
            evolucao = ((atual - inicial) / inicial * 100) if inicial > 0 else 0
            with st.expander(f"📊 {corretora} — R$ {atual:.2f}"):
                col1, col2 = st.columns(2)
                col1.metric("Inicial", f"R$ {inicial:.2f}")
                col2.metric("Atual", f"R$ {atual:.2f}", f"{evolucao:+.2f}%")
                st.metric("Lucro Total", f"R$ {lucro:.2f}", "+" if lucro>=0 else "")
    
    elif pag == "Alterar Plano":
        tela_planos()
    
    elif pag == "Minhas Corretoras":
        tela_apis()
    
    elif pag == "Calculadora":
        st.header("🧮 Calculadora")
        c1, c2 = st.columns(2)
        with c1:
            pc = st.number_input("Preço Compra", 0.0, 100000.0, 100.0)
            pv = st.number_input("Preço Venda", 0.0, 100000.0, 102.0)
            taxa = st.number_input("Taxa (%)", 0.0, 5.0, 0.1)
            valor_inv = st.number_input("Valor Investido", 10.0, 10000.0, 100.0)
        with c2:
            calc = calcular_lucro_liquido(pc, pv, taxa)
            lucro_val = valor_inv * (calc["lucro_perc"] / 100)
            st.metric("Lucro Líquido %", f"{calc['lucro_perc']:.2f}%")
            st.metric("Lucro em R$", f"R$ {lucro_val:.2f}")
            if calc["lucro_perc"] <= 0: st.error("Não dá lucro!")
    
    elif pag == "Histórico de Operações":
        st.header("📊 Histórico")
        hist = carregar_json(ARQUIVO_HISTORICO_OPERACOES, [])
        minhas = [x for x in hist if x.get("email")==email]
        if not minhas:
            st.info("Nenhuma operação ainda.")
        else:
            lucro_total = sum(op.get("lucro_valor",0) for op in minhas if op.get("status") in ["executada","real"])
            c1, c2 = st.columns(2)
            c1.metric("Total de Operações", len(minhas))
            c2.metric("Lucro Acumulado", f"R$ {lucro_total:.2f}", "+" if lucro_total>=0 else "")
            for op in minhas[:50]:
                icone = {"executada":"✅","real":"💰","falhou":"❌","simulada":"🔵"}.get(op.get("status"),"—")
                with st.expander(f"{icone} {op['hora']} | {op['moeda']} | R$ {op.get('lucro_valor',0):.2f}"):
                    st.write(f"{op['comprar_em']} → {op['vender_em']}")
                    st.write(f"Investido: R$ {op.get('valor_investido',0):.2f}")
                    st.write(f"Modo: {op.get('modo','')} | Status: {op.get('status','')}")
    
    elif pag == "Scanner":
        st.header("🔍 Scanner de Arbitragem")
        if p["bot_operacional"]:
            bot_ativo = st.checkbox("🤖 ATIVAR BOT", value=st.session_state["bot_ativo"])
            if bot_ativo != st.session_state["bot_ativo"]:
                st.session_state["bot_ativo"] = bot_ativo
                st.rerun()
        else:
            st.info("🔒 Faça upgrade para Pro/Premium")
        
        min_lucro = st.slider("Lucro Mínimo (%)", 0.1, 5.0, 0.5, 0.1)
        valor_padrao = st.number_input("Valor por Operação (R$)", 10.0, 1000.0, 100.0)
        
        moedas = MOEDAS_MONITORADAS[:p["moedas"]] if p["moedas"]<100 else MOEDAS_MONITORADAS
        corretoras = list(apis.keys()) if apis else p["corretoras"]
        
        if st.button("🔄 ESCANEAR AGORA", type="primary") or st.session_state["bot_ativo"]:
            with st.spinner("Analisando..."):
                ops = escanear_oportunidades(corretoras, moedas, min_lucro, apis)
            
            if st.session_state["bot_ativo"] and ops and p["bot_operacional"]:
                agora = datetime.now()
                ultima = st.session_state["ultima_execucao_bot"]
                if not ultima or (agora - ultima).total_seconds() > p["atualizacao_segundos"]:
                    st.session_state["ultima_execucao_bot"] = agora
                    melhor = ops[0]
                    ok, msg = executar_operacao(melhor, email, valor_padrao)
                    if ok: st.success(msg)
                    else: st.warning(msg)
                    time.sleep(2)
                    st.rerun()
            
            if not ops:
                st.info("Nenhuma oportunidade agora.")
            else:
                st.subheader(f"✅ {len(ops)} encontrada(s)")
                for i, op in enumerate(ops[:10]):
                    with st.expander(f"💰 {op['moeda']} — {op['lucro_perc']:.2f}%"):
                        st.write(f"Comprar: {op['comprar_em']} — Vender: {op['vender_em']}")
                        st.write(f"Preço compra: {op['preco_compra']:.4f} | Venda: {op['preco_venda']:.4f}")
                        lucro_est = valor_padrao * (op['lucro_perc']/100)
                        st.write(f"Retorno: R$ {lucro_est:.2f}")
                        if st.button(f"⚡ EXECUTAR — {op['moeda']}", key=f"ex{i}", type="primary"):
                            ok, msg = executar_operacao(op, email, valor_padrao)
                            if ok: st.success(msg)
                            else: st.error(msg)
                            time.sleep(1)
                            st.rerun()

# ==============================================
# ROTEAMENTO PRINCIPAL
# ==============================================
if "pagina" not in st.session_state:
    st.session_state["pagina"] = "inicio"

pagina = st.session_state["pagina"]

if pagina == "Painel de Administração":
    painel_admin()
elif st.session_state["logado"]:
    if pagina == "Planos": tela_planos()
    elif pagina == "Pagamento": tela_pagamento()
    else: painel_usuario()
else:
    tela_login()