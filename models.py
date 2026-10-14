from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Ticket:
    """Chamado/alerta com informações de contexto."""
    id: str
    ativo: Optional[str] = None
    serviço: Optional[str] = None
    sintomas: Optional[list[str]] = field(default_factory=lambda: None)
    descrição: Optional[str] = None
    timestamp: Optional[datetime] = None


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
