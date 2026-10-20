from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


STATUS_VALIDOS = ("aberto", "em_andamento", "resolvido", "encerrado")


def validar_status(status: str) -> None:
    """Levanta ValueError se o status não for um dos valores permitidos."""
    if status not in STATUS_VALIDOS:
        raise ValueError(f"Status inválido: {status}")


@dataclass
class Ticket:
    """Chamado/alerta com informações de contexto."""
    id: str
    ativo: Optional[str] = None
    serviço: Optional[str] = None
    sintomas: Optional[list[str]] = field(default_factory=lambda: None)
    descrição: Optional[str] = None
    timestamp: Optional[datetime] = None
    status: str = "aberto"
    resolvido_em: Optional[datetime] = None
    encerrado_em: Optional[datetime] = None

    def __post_init__(self):
        validar_status(self.status)


@dataclass
class CorrelationReason:
    """Motivo individual para uma pontuação de correlação."""
    tipo: str  # "ativo", "serviço", "sintoma", "temporal", "descrição"
    peso: int  # 0-30
    explicação: str


@dataclass
class CorrelationResult:
    """Resultado da comparação entre dois chamados."""
    ticket1_id: str
    ticket2_id: str
    score: int  # 0-100
    reasons: list[CorrelationReason]
    correlacionado: bool  # True se score >= 60
