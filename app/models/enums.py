from enum import Enum


class CargoUsuario(str, Enum):
    ADMIN = "ADMIN"
    GERENTE = "GERENTE"
    FUNCIONARIO = "FUNCIONARIO"


class StatusAgendamento(str, Enum):
    PENDENTE = "PENDENTE"
    CONFIRMADO = "CONFIRMADO"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"


class OrigemAgendamento(str, Enum):
    IA = "IA"
    FUNCIONARIO = "FUNCIONARIO"
    SITE = "SITE"
    WHATSAPP = "WHATSAPP"


class FormaPagamento(str, Enum):
    DINHEIRO = "DINHEIRO"
    PIX = "PIX"
    CARTAO_DEBITO = "CARTAO_DEBITO"
    CARTAO_CREDITO = "CARTAO_CREDITO"
    BOLETO = "BOLETO"


class OrigemConversa(str, Enum):
    WHATSAPP = "WHATSAPP"
    SITE = "SITE"
    INSTAGRAM = "INSTAGRAM"


class StatusConversa(str, Enum):
    ABERTA = "ABERTA"
    EM_ATENDIMENTO = "EM_ATENDIMENTO"
    FINALIZADA = "FINALIZADA"


class RemetenteMensagem(str, Enum):
    CLIENTE = "CLIENTE"
    IA = "IA"
    FUNCIONARIO = "FUNCIONARIO"
    GERENTE = "GERENTE"


class TipoMensagem(str, Enum):
    TEXTO = "TEXTO"
    IMAGEM = "IMAGEM"
    AUDIO = "AUDIO"
    DOCUMENTO = "DOCUMENTO"


class StatusCliente(str, Enum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"
    BLOQUEADO = "BLOQUEADO"


class StatusAssinatura(str, Enum):
    TRIAL = "TRIAL"
    ATIVA = "ATIVA"
    INADIMPLENTE = "INADIMPLENTE"
    CANCELADA = "CANCELADA"


class AtorLog(str, Enum):
    USUARIO = "USUARIO"
    IA = "IA"
    SISTEMA = "SISTEMA"


class TipoIntegracao(str, Enum):
    WHATSAPP = "WHATSAPP"
    INSTAGRAM = "INSTAGRAM"
    FACEBOOK = "FACEBOOK"
    SITE = "SITE"
