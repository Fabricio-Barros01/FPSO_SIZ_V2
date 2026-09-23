"""Registro de equipamentos e métodos (port de src/registry.jl). Um método registrado
aparece na CLI e no catálogo sem editar a interface."""
from fpso_siz.core.contrato import Equipamento, MetodoDimensionamento

_EQUIPAMENTOS = {}
_METODOS = {}


def register(obj):
    """Registra equipamento ou método; idempotente (mesmo id substitui)."""
    if isinstance(obj, Equipamento):
        _EQUIPAMENTOS[obj.method_id] = obj
        _METODOS.setdefault(obj.method_id, [])
    elif isinstance(obj, MetodoDimensionamento):
        lista = _METODOS.setdefault(obj.applies_to().method_id, [])
        for i, m in enumerate(lista):
            if m.method_id == obj.method_id:
                lista[i] = obj
                break
        else:
            lista.append(obj)
    else:
        raise TypeError(f"não registrável: {type(obj).__name__}")
    return obj


def equipments():
    return [_EQUIPAMENTOS[k] for k in sorted(_EQUIPAMENTOS)]


def methods_for(eq):
    return list(_METODOS.get(eq if isinstance(eq, str) else eq.method_id, []))


def equipment(eq_id):
    return _EQUIPAMENTOS.get(eq_id)


def sizing_method(eq_id, m_id):
    return next((m for m in _METODOS.get(eq_id, []) if m.method_id == m_id), None)


def resolver(eq_id, m_id=None):
    """(equipamento, método) a partir dos ids; sem `m_id`, o primeiro método registrado.
    ValueError com a lista do que existe, se não houver."""
    eq = equipment(eq_id)
    if eq is None:
        raise ValueError(f"equipamento desconhecido {eq_id!r}; registrados: "
                         f"{', '.join(e.method_id for e in equipments())}")
    metodos = methods_for(eq)
    if not metodos:
        raise ValueError(f"'{eq.label}' não tem método registrado")
    if m_id is None:
        return eq, metodos[0]
    m = sizing_method(eq_id, m_id)
    if m is None:
        raise ValueError(f"método desconhecido {m_id!r} para '{eq.label}'; registrados: "
                         f"{', '.join(x.method_id for x in metodos)}")
    return eq, m


def _reset():
    _EQUIPAMENTOS.clear()
    _METODOS.clear()
