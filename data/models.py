"""
data/models.py
==============

Modelos ORM SQLAlchemy mapeando o schema bk_malha_terra do Neon.
Espelha o DDL em migrations/001_schema_inicial.sql.

Convenção:
- Nomes de tabelas em snake_case (igual ao banco)
- Datetimes em UTC
- Cascade delete habilitado de projeto → filhos
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base de todos os modelos do BK Malha de Terra."""
    pass


# ============================================================
# PROJETOS
# ============================================================

class Projeto(Base):
    __tablename__ = "projetos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente: Mapped[str] = mapped_column(String(200), nullable=False)
    nome_projeto: Mapped[str] = mapped_column(String(300), nullable=False)
    numero_projeto: Mapped[str] = mapped_column(String(50), nullable=False)
    revisao: Mapped[str] = mapped_column(String(10), nullable=False, default="00")
    responsavel_tecnico: Mapped[Optional[str]] = mapped_column(String(200))
    crea_responsavel: Mapped[Optional[str]] = mapped_column(String(50))
    concessionaria: Mapped[Optional[str]] = mapped_column(String(50))
    data_calculo: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    observacoes: Mapped[Optional[str]] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relacionamentos com cascade
    medicoes_wenner: Mapped[list["SoloWenner"]] = relationship(
        back_populates="projeto",
        cascade="all, delete-orphan",
        order_by="SoloWenner.ponto",
    )
    dados_entrada: Mapped[Optional["DadosEntrada"]] = relationship(
        back_populates="projeto",
        cascade="all, delete-orphan",
        uselist=False,
    )
    resultado: Mapped[Optional["Resultado"]] = relationship(
        back_populates="projeto",
        cascade="all, delete-orphan",
        uselist=False,
    )
    relatorios: Mapped[list["RelatorioGerado"]] = relationship(
        back_populates="projeto",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Projeto #{self.id} {self.numero_projeto}-{self.revisao} "
            f"{self.cliente}: {self.nome_projeto}>"
        )

    @property
    def identificador(self) -> str:
        """Identificador legível: 'PRJ-2026-001 R00'."""
        return f"{self.numero_projeto} R{self.revisao}"


# ============================================================
# SOLO - MEDIÇÕES WENNER
# ============================================================

class SoloWenner(Base):
    __tablename__ = "solos_wenner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False
    )
    ponto: Mapped[int] = mapped_column(Integer, nullable=False)
    espacamento_m: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    resistencia_ohm: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    rho_aparente: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))

    projeto: Mapped["Projeto"] = relationship(back_populates="medicoes_wenner")


# ============================================================
# DADOS DE ENTRADA
# ============================================================

class DadosEntrada(Base):
    __tablename__ = "dados_entrada"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projetos.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )

    # Geometria
    largura_m: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    comprimento_m: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    profundidade_malha_m: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=0.50
    )
    espac_malha_principal_m: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    espac_malha_juncao_m: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Brita
    brita_espessura_m: Mapped[float] = mapped_column(
        Numeric(5, 3), nullable=False, default=0.10
    )
    brita_resistividade_ohm: Mapped[float] = mapped_column(
        Numeric(8, 1), nullable=False, default=3000.0
    )

    # Hastes
    haste_comprimento_m: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=3.0
    )
    haste_diametro_mm: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False, default=15.875
    )

    # Condutor
    condutor_material: Mapped[str] = mapped_column(
        String(20), nullable=False, default="cobre_nu"
    )
    condutor_bitola_mm2: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))

    # Curto
    i_falta_3i0_ka: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    tempo_eliminacao_s: Mapped[float] = mapped_column(
        Numeric(5, 3), nullable=False, default=0.5
    )
    sf_div_corrente: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.6
    )
    xr_ratio: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    df_decremento: Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    peso_pessoa_kg: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    projeto: Mapped["Projeto"] = relationship(back_populates="dados_entrada")


# ============================================================
# RESULTADOS
# ============================================================

class Resultado(Base):
    __tablename__ = "resultados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projetos.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )

    # Estratificação
    rho1_ohm_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    rho2_ohm_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    h1_m: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    rho_equivalente: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Condutor
    bitola_calculada_mm2: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    bitola_adotada_mm2: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))

    # Tensões admissíveis
    cs_brita: Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    etoque_admissivel_v: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    epasso_admissivel_v: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Corrente
    df_decremento: Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    ig_corrente_malha_a: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Resistência
    rg_sverak_ohm: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    rg_schwarz_ohm: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    rg_adotado_ohm: Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    gpr_v: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))

    # Tensões calculadas
    em_tensao_malha_v: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    es_tensao_passo_v: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Geometria final
    num_hastes: Mapped[Optional[int]] = mapped_column(Integer)
    comprimento_total_cabo_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    posicoes_hastes_json: Mapped[Optional[dict]] = mapped_column(JSON)

    # Verificação
    atende_toque: Mapped[Optional[bool]] = mapped_column(Boolean)
    atende_passo: Mapped[Optional[bool]] = mapped_column(Boolean)
    atende_geral: Mapped[Optional[bool]] = mapped_column(Boolean)
    margem_toque_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    margem_passo_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))

    json_completo: Mapped[Optional[dict]] = mapped_column(JSON)
    calculado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    projeto: Mapped["Projeto"] = relationship(back_populates="resultado")


# ============================================================
# RELATÓRIOS GERADOS
# ============================================================

class RelatorioGerado(Base):
    __tablename__ = "relatorios_gerados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False
    )
    nome_arquivo: Mapped[str] = mapped_column(String(300), nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    gerado_por: Mapped[Optional[str]] = mapped_column(String(200))

    projeto: Mapped["Projeto"] = relationship(back_populates="relatorios")
