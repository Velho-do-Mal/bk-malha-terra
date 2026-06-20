"""
data/models.py — BK Malha de Terra v2 (Multi-Tenant)
=====================================================
Adiciona: Tenant, Usuario, tenant_id em Projeto, cp_crescimento em DadosEntrada.
"""

from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── TENANT ──────────────────────────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id:               Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_empresa:     Mapped[str]      = mapped_column(String(300), nullable=False)
    cnpj:             Mapped[Optional[str]] = mapped_column(String(18))
    email_contato:    Mapped[str]      = mapped_column(String(254), nullable=False, unique=True)
    telefone:         Mapped[Optional[str]] = mapped_column(String(20))
    plano:            Mapped[str]      = mapped_column(String(20), nullable=False, default="trial")
    ativo:            Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True)
    max_projetos:     Mapped[int]      = mapped_column(Integer, nullable=False, default=3)
    max_usuarios:     Mapped[int]      = mapped_column(Integer, nullable=False, default=2)
    trial_expira_em:  Mapped[Optional[datetime]] = mapped_column(DateTime)
    criado_em:        Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em:    Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuarios:  Mapped[list["Usuario"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    projetos:  Mapped[list["Projeto"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

    @property
    def plano_label(self) -> str:
        return {"trial": "Trial (14 dias)", "pro": "Pro", "enterprise": "Enterprise"}.get(self.plano, self.plano)


# ─── USUARIO ─────────────────────────────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id:     Mapped[int]      = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    nome:          Mapped[str]      = mapped_column(String(200), nullable=False)
    email:         Mapped[str]      = mapped_column(String(254), nullable=False, unique=True)
    senha_hash:    Mapped[str]      = mapped_column(String(72), nullable=False)
    role:          Mapped[str]      = mapped_column(String(20), nullable=False, default="engenheiro")
    crea:          Mapped[Optional[str]] = mapped_column(String(50))
    ativo:         Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True)
    criado_em:     Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ultimo_acesso: Mapped[Optional[datetime]] = mapped_column(DateTime)

    tenant:   Mapped["Tenant"]         = relationship(back_populates="usuarios")
    projetos: Mapped[list["Projeto"]]  = relationship(back_populates="criado_por", foreign_keys="Projeto.criado_por_id")

    @property
    def role_label(self) -> str:
        return {"admin": "Administrador", "engenheiro": "Engenheiro", "viewer": "Visualizador"}.get(self.role, self.role)


# ─── PROJETO ─────────────────────────────────────────────────────────────────

class Projeto(Base):
    __tablename__ = "projetos"

    id:                  Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    # ── Multi-tenancy ──
    tenant_id:           Mapped[int]      = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    criado_por_id:       Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"))
    # ── Identificação ──
    cliente:             Mapped[str]      = mapped_column(String(200), nullable=False)
    nome_projeto:        Mapped[str]      = mapped_column(String(300), nullable=False)
    numero_projeto:      Mapped[str]      = mapped_column(String(50), nullable=False)
    revisao:             Mapped[str]      = mapped_column(String(10), nullable=False, default="00")
    responsavel_tecnico: Mapped[Optional[str]] = mapped_column(String(200))
    crea_responsavel:    Mapped[Optional[str]] = mapped_column(String(50))
    concessionaria:      Mapped[Optional[str]] = mapped_column(String(50))
    data_calculo:        Mapped[date]     = mapped_column(Date, nullable=False, default=date.today)
    observacoes:         Mapped[Optional[str]] = mapped_column(Text)
    criado_em:           Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em:       Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tenant:      Mapped["Tenant"]               = relationship(back_populates="projetos")
    criado_por:  Mapped[Optional["Usuario"]]    = relationship(back_populates="projetos", foreign_keys=[criado_por_id])
    medicoes_wenner: Mapped[list["SoloWenner"]] = relationship(back_populates="projeto", cascade="all, delete-orphan", order_by="SoloWenner.ponto")
    dados_entrada:   Mapped[Optional["DadosEntrada"]] = relationship(back_populates="projeto", cascade="all, delete-orphan", uselist=False)
    resultado:       Mapped[Optional["Resultado"]]    = relationship(back_populates="projeto", cascade="all, delete-orphan", uselist=False)
    relatorios:      Mapped[list["RelatorioGerado"]]  = relationship(back_populates="projeto", cascade="all, delete-orphan")

    @property
    def identificador(self) -> str:
        return f"{self.numero_projeto} R{self.revisao}"


# ─── SOLO WENNER ─────────────────────────────────────────────────────────────

class SoloWenner(Base):
    __tablename__ = "solos_wenner"

    id:              Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto_id:      Mapped[int]            = mapped_column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False)
    ponto:           Mapped[int]            = mapped_column(Integer, nullable=False)
    espacamento_m:   Mapped[float]          = mapped_column(Numeric(6, 2), nullable=False)
    resistencia_ohm: Mapped[float]          = mapped_column(Numeric(10, 4), nullable=False)
    rho_aparente:    Mapped[Optional[float]]= mapped_column(Numeric(10, 4))

    projeto: Mapped["Projeto"] = relationship(back_populates="medicoes_wenner")


# ─── DADOS DE ENTRADA ─────────────────────────────────────────────────────────

class DadosEntrada(Base):
    __tablename__ = "dados_entrada"

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto_id: Mapped[int] = mapped_column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False, unique=True)

    largura_m:                Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    comprimento_m:            Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    profundidade_malha_m:     Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.50)
    espac_malha_principal_m:  Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    espac_malha_juncao_m:     Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    brita_espessura_m:        Mapped[float] = mapped_column(Numeric(5, 3), nullable=False, default=0.10)
    brita_resistividade_ohm:  Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, default=3000.0)
    haste_comprimento_m:      Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=3.0)
    haste_diametro_mm:        Mapped[float] = mapped_column(Numeric(6, 3), nullable=False, default=15.875)
    condutor_material:        Mapped[str]   = mapped_column(String(20), nullable=False, default="cobre_nu")
    condutor_bitola_mm2:      Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    i_falta_3i0_ka:           Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    tempo_eliminacao_s:       Mapped[float] = mapped_column(Numeric(5, 3), nullable=False, default=0.5)
    sf_div_corrente:          Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.6)
    xr_ratio:                 Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    df_decremento:            Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    peso_pessoa_kg:           Mapped[int]   = mapped_column(Integer, nullable=False, default=50)
    # ── P0: fator de crescimento da corrente de falta ──
    cp_crescimento:           Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=1.00)

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    projeto:   Mapped["Projeto"] = relationship(back_populates="dados_entrada")


# ─── RESULTADO ───────────────────────────────────────────────────────────────

class Resultado(Base):
    __tablename__ = "resultados"

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto_id: Mapped[int] = mapped_column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False, unique=True)

    rho1_ohm_m:             Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    rho2_ohm_m:             Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    h1_m:                   Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    rho_equivalente:        Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    bitola_calculada_mm2:   Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    bitola_adotada_mm2:     Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    atende_condutor:        Mapped[Optional[bool]]  = mapped_column(Boolean)
    cs_brita:               Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    etoque_admissivel_v:    Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    epasso_admissivel_v:    Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    df_decremento:          Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    cp_crescimento:         Mapped[Optional[float]] = mapped_column(Numeric(4, 2))
    ig_corrente_malha_a:    Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    rg_sverak_ohm:          Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    rg_schwarz_ohm:         Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    rg_adotado_ohm:         Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    gpr_v:                  Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    em_tensao_malha_v:      Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    es_tensao_passo_v:      Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    num_hastes:             Mapped[Optional[int]]   = mapped_column(Integer)
    comprimento_total_cabo_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    posicoes_hastes_json:   Mapped[Optional[dict]]  = mapped_column(JSON)
    atende_toque:           Mapped[Optional[bool]]  = mapped_column(Boolean)
    atende_passo:           Mapped[Optional[bool]]  = mapped_column(Boolean)
    atende_geral:           Mapped[Optional[bool]]  = mapped_column(Boolean)
    margem_toque_pct:       Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    margem_passo_pct:       Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    json_completo:          Mapped[Optional[dict]]  = mapped_column(JSON)
    calculado_em:           Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow)

    projeto: Mapped["Projeto"] = relationship(back_populates="resultado")


# ─── RELATÓRIO ───────────────────────────────────────────────────────────────

class RelatorioGerado(Base):
    __tablename__ = "relatorios_gerados"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    projeto_id:   Mapped[int]      = mapped_column(Integer, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False)
    nome_arquivo: Mapped[str]      = mapped_column(String(300), nullable=False)
    gerado_em:    Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    gerado_por:   Mapped[Optional[str]] = mapped_column(String(200))

    projeto: Mapped["Projeto"] = relationship(back_populates="relatorios")
