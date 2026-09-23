# Exporta fixtures numéricas do FPSO_Siz Julia para o oráculo dos equipamentos (F5+).
#
# Roda SOBRE UM SNAPSHOT (`git archive <commit>` extraído numa pasta temporária); o
# repositório Julia nunca é tocado. Uso (ver tools/exportar_fixtures_julia.sh):
#
#     julia --project=<snapshot> tools/exportar_fixtures_julia.jl <snapshot> <commit> <saida>
#
# Para cada box de config/catalogo.toml: descritores do método, constantes do TOML,
# expansão do arquivo de exemplo em cantos e o `size_envelope` completo (linhas da
# varredura, casos individuais com varredura e rastro, cartão de resultados). JSON com
# chaves ordenadas, floats em repr exato (ida e volta) e NaN/Inf como texto.

using TOML
snapshot, commit, saida = ARGS
push!(LOAD_PATH, snapshot)
using FPSOSiz
const F = FPSOSiz

# ------------------------------------------------------------------ JSON mínimo
esc(s) = replace(String(s), "\\" => "\\\\", "\"" => "\\\"", "\n" => "\\n", "\t" => "\\t", "\r" => "\\r")
js(io, x::Nothing) = print(io, "null")
js(io, x::Bool) = print(io, x ? "true" : "false")
js(io, x::Integer) = print(io, x)
js(io, x::AbstractFloat) = isnan(x) ? print(io, "\"NaN\"") : isinf(x) ? print(io, x > 0 ? "\"Inf\"" : "\"-Inf\"") : print(io, repr(Float64(x)))
js(io, x::Union{AbstractString,Symbol}) = print(io, '"', esc(x), '"')
function js(io, x::Union{AbstractVector,Tuple})
    print(io, "[")
    for (i, v) in enumerate(x)
        i > 1 && print(io, ",")
        js(io, v)
    end
    print(io, "]")
end
js(io, x::NamedTuple) = js(io, Dict(string(k) => v for (k, v) in pairs(x)))
function js(io, x::AbstractDict)
    print(io, "{")
    for (i, k) in enumerate(sort!(collect(keys(x)); by = string))
        i > 1 && print(io, ",")
        js(io, string(k)); print(io, ":"); js(io, x[k])
    end
    print(io, "}")
end
js(io, x) = error("sem serialização para $(typeof(x))")

# ------------------------------------------------------------------ conversões
spec(s::F.ParameterSpec) = Dict("key" => s.key, "label" => s.label, "unit" => s.unit, "default" => s.default,
    "min" => s.min, "max" => s.max, "advanced" => s.advanced, "note" => s.note, "group" => s.group,
    "instance" => s.instance)
campo(f::F.ResultField) = Dict("label" => f.label, "value" => f.value, "unit" => f.unit, "digits" => f.digits,
    "highlight" => f.highlight, "status" => f.status)
traco(t::F.CalcTrace) = [Dict("block" => e.block, "eq" => e.eq, "var" => e.var, "formula" => e.formula,
    "value" => e.value, "unit" => e.unit) for e in t.entries]
linha_sweep(r) = Dict("x" => r.x, "y" => r.y, "per_constraint" => r.per_constraint, "derivados" => r.derivados,
    "governing" => r.governing, "ok" => r.ok, "tem_presentation" => r.presentation !== nothing)
unico(r::F.SizingResult) = Dict("feasible" => r.feasible, "message" => r.message, "x" => r.x, "y" => r.y,
    "derivados" => r.derivados, "governing" => r.governing, "ceiling" => r.ceiling,
    "ceiling_mechanism" => r.ceiling_mechanism, "method_id" => r.method_id,
    "sweep" => [linha_sweep(s) for s in r.sweep], "trace" => traco(r.trace))
linha_env(r) = Dict("x" => r.x, "y" => r.y, "derivados" => r.derivados, "governing" => r.governing,
    "driver_case" => r.driver_case, "per_case_y" => r.per_case_y, "ok" => r.ok,
    "tem_presentation" => r.presentation !== nothing)
envelope(r::F.EnvelopeResult) = Dict("feasible" => r.feasible, "message" => r.message, "x" => r.x, "y" => r.y,
    "derivados" => r.derivados, "governing" => r.governing, "driver_case" => r.driver_case,
    "ceiling" => r.ceiling, "ceiling_case" => r.ceiling_case, "ceiling_mechanism" => r.ceiling_mechanism,
    "case_names" => r.case_names, "rows" => [linha_env(x) for x in r.rows], "slack" => r.slack,
    "per_case" => [unico(p) for p in r.per_case])
casoval(v::F.Interval) = [v.lo, v.hi]
casoval(v) = v

const EXEMPLO = Dict("separator" => "exemplo_alves_komesu", "knockout" => "exemplo_knockout",
    "treater" => "exemplo_tratador", "pump" => "exemplo_bomba", "exchanger" => "exemplo_trocador",
    "pinch" => "exemplo_pinch_kemp")

function exportar_box(b)
    eq = F.equipment(Symbol(b["equipment"]))
    m = F.sizing_method(Symbol(b["equipment"]), Symbol(b["method"]))
    out = Dict{String,Any}("box" => b["id"], "equipment" => b["equipment"], "method" => b["method"],
        "label" => F.label(m), "equipment_label" => F.label(eq))
    out["parameters"] = [spec(s) for s in F.parameters(m)]
    out["stream_parameters"] = [spec(s) for s in F.stream_parameters(m)]
    out["stream_keys"] = collect(F.stream_keys(m))
    out["parameter_groups"] = F.parameter_groups(m)
    out["global_keys"] = F.global_keys(m)
    out["action_label"] = F.action_label(m)
    out["requirement_spec"] = collect(F.requirement_spec(m))
    haskey(EXEMPLO, b["equipment"]) || return out
    out["constants"] = F.constants(F.method_config(m))
    out["sweep_columns"] = [Dict("label" => c.label, "key" => c.key, "digits" => c.digits) for c in F.sweep_columns(m)]
    out["trace_blocks"] = [Dict("key" => k, "title" => v) for (k, v) in F.trace_blocks(m)]
    arq = EXEMPLO[b["equipment"]]
    cs = F.case_set_from_config(TOML.parsefile(joinpath(snapshot, "config", "cases", arq * ".toml")))
    out["exemplo"] = arq
    out["casos"] = [Dict("name" => c.name, "enabled" => c.enabled,
        "values" => Dict(string(k) => casoval(v) for (k, v) in c.values)) for c in cs.cases]
    out["expansao"] = [Dict("name" => n, "values" => v) for (n, v) in F.expand(cs)]
    r = F.size_envelope(eq, m, cs)
    out["envelope"] = envelope(r)
    out["result_fields"] = [campo(f) for f in F.result_fields(m, r)]
    out["governing_summary"] = F.governing_summary(m, r)
    return out
end

# strings de número no formato do Julia (mensagens citam valores assim)
function formatos()
    xs = [0.0, -0.0, 1.0, 0.1, 2.5, 100.0, 12345.678, 1.0e5, 1.0e6, 123456.0, 1234567.0, 1.0e-4, 1.0e-5, 3.0e-7,
          9124.4, 18.59, 1.0e15, 1.0e16, -2.5e-11, 6300.0, 0.30000000000000004, 1/3]
    Dict("string" => [[x, string(x)] for x in xs],
         "round2" => [[x, string(round(x, digits = 2))] for x in xs],
         "round0" => [[x, string(round(x, digits = 0))] for x in xs if isfinite(x)])
end

mkpath(saida)
cat = TOML.parsefile(joinpath(snapshot, "config", "catalogo.toml"))
arquivos = String[]
for b in cat["box"]
    d = exportar_box(b)
    nome = "$(b["id"]).json"
    open(io -> (js(io, d); println(io)), joinpath(saida, nome), "w")
    push!(arquivos, nome)
    println(nome)
end
open(io -> (js(io, formatos()); println(io)), joinpath(saida, "formatos_julia.json"), "w")
push!(arquivos, "formatos_julia.json")
open(joinpath(saida, "manifesto.json"), "w") do io
    js(io, Dict("commit" => commit, "julia" => string(VERSION), "gerador" => "tools/exportar_fixtures_julia.jl",
        "arquivos" => arquivos, "stream_parameters" => [spec(s) for s in F.stream_parameters()]))
    println(io)
end
