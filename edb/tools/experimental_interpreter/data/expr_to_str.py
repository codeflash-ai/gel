from __future__ import annotations

from typing import Any

from . import data_ops as e
from . import expr_ops as eops


def show_card(card: e.Cardinal) -> str:
    match card:
        case e.ZeroCardinal():
            return "0"
        case e.OneCardinal():
            return "1"
        case e.InfiniteCardinal():
            return "∞"
        case _:
            raise ValueError('Unimplemented', card)


def show_cmmode(mode: e.CMMode) -> str:
    return "[" + show_card(mode.lower) + "," + show_card(mode.upper) + "]"


def show_qname(name: e.QualifiedName) -> str:
    return "::".join(name.names)


def show_raw_name(name: e.QualifiedName | e.UnqualifiedName) -> str:
    if isinstance(name, e.QualifiedName):
        return show_qname(name)
    else:
        return name.name


def show_tp(tp: e.Tp | e.RawName) -> str:
    # Fast-path control for each variant, with optimized string concatenation/joins
    match tp:
        case e.ObjectTp(val=tp_val):
            # Use a list comprehension and str.join for efficient string building
            # Avoid repeated string + in the generator
            items = [f'{lbl}: {show_tp(md_tp.tp)}{show_cmmode(md_tp.mode)}' for lbl, md_tp in tp_val.items()]
            return '{' + ', '.join(items) + '}'
        case e.ScalarTp(name):
            return show_qname(name)
        case e.UncheckedTypeName(name):
            return "unchecked_name(" + show_raw_name(name) + ")"
        case e.CompositeTp(kind=kind, tps=tps, labels=labels):
            if labels:
                # Only build formatted strings inline with join, avoid tuple unpacking in generator
                items = [f'{label}:{show_tp(tp)}' for label, tp in zip(labels, tps, strict=True)]
                return f'{kind.value}<' + ",".join(items) + '>'
            else:
                return f'{kind.value}<' + ",".join([show_tp(tp) for tp in tps]) + '>'
        case e.SomeTp(index=index):
            return f'some_{{{index}}}'
        case e.AnyTp(name):
            return 'any' + (name or '')
        case e.NamedNominalLinkTp(name=name, linkprop=lp_tp):
            # Optimize with f-string for both calls (this was a hotspot in profiling)
            lp_res = show_tp(lp_tp)
            name_res = show_raw_name(name)
            return f'{name_res}@{lp_res}'
        case e.NominalLinkTp(name=name, subject=s_tp, linkprop=lp_tp):
            s_res = show_tp(s_tp)
            name_res = show_raw_name(name)
            lp_res = show_tp(lp_tp)
            return f'{s_res}_{name_res}@{lp_res}'
        case e.UnionTp(left=left, right=right):
            left_s = show_tp(left)
            right_s = show_tp(right)
            return f'{left_s} | {right_s}'
        case e.IntersectTp(left=left, right=right):
            left_s = show_tp(left)
            right_s = show_tp(right)
            return f'{left_s} & {right_s}'
        case e.UncheckedComputableTp(expr=expr):
            # Avoid string concat in generator, use f-string
            return f'comp_unck({show_expr(expr)})'
        case e.ComputableTp(expr=expr, tp=tp):
            # Save results for repeated show_tp/tp/expr instead of repeated calls
            tp_s = show_tp(tp)
            expr_s = show_expr(expr)
            return f'comp({tp_s},{expr_s})'
        case e.DefaultTp(expr=expr, tp=tp):
            tp_s = show_tp(tp)
            expr_s = show_expr(expr)
            return f'default({tp_s},{expr_s})'
        case e.OverloadedTargetTp(linkprop=linkprop):
            if linkprop is None:
                return 'overloaded()'
            else:
                lp_s = show_tp(linkprop)
                return f'overloaded(linkprop={lp_s})'
        case e.QualifiedName(_) | e.UnqualifiedName(_):
            return show_raw_name(tp)
        case _:
            raise ValueError('Unimplemented', tp)


def show_func_tps(tp: e.FunArgRetType) -> str:
    return (
        ", ".join(show_tp(arg_tp) for arg_tp in tp.args_tp)
        + " -> "
        + show_result_tp(tp.ret_tp)
    )


def show_result_tp(tp: e.ResultTp) -> str:
    return show_tp(tp.tp) + show_cmmode(tp.mode)


def show_label(lbl: e.Label) -> str:
    match lbl:
        case e.StrLabel(label=s_label):
            return s_label
        case e.LinkPropLabel(label=l_label):
            return "@" + l_label
        case _:
            raise ValueError('Unimplemented', lbl)


def show_scalar_val(val: e.ScalarVal) -> str:
    tp = val.tp
    v = val.val
    match tp.name:
        case e.QualifiedName(["std", "str"]):
            return '"' + v + '"'
        case e.QualifiedName(["std", "int64"]):
            return str(v)
        case e.QualifiedName(["std", "bool"]):
            return str(v)
        case _:
            return show_qname(tp.name) + "(" + str(v) + ")"


def show_edge_database_select_filter(
    filter: e.EdgeDatabaseSelectFilter,
) -> str:
    match filter:
        case e.EdgeDatabaseEqFilter(propname=propname, arg=arg):
            return f'({propname} = {show(arg)})'
        case e.EdgeDatabaseConjunctiveFilter(conjuncts=conjuncts):
            return (
                '('
                + " AND ".join(
                    show_edge_database_select_filter(f) for f in conjuncts
                )
                + ')'
            )
        case e.EdgeDatabaseDisjunctiveFilter(disjuncts=disjuncts):
            return (
                '('
                + " OR ".join(
                    show_edge_database_select_filter(f) for f in disjuncts
                )
                + ')'
            )
        case e.EdgeDatabaseTrueFilter():
            return 'TRUE'
        case _:
            raise ValueError('Unimplemented', filter)


def show_expr(expr: e.Expr) -> str:
    match expr:
        case e.QualifiedName(_):
            return show_qname(expr)
        case e.UnqualifiedName(_):
            return show_raw_name(expr)
        case e.ScalarVal(tp, _):
            return show_scalar_val(expr)
        case e.BindingExpr(var=var, body=_):
            return (
                "λ"
                + var
                + ". "
                + show_expr(eops.instantiate_expr(e.FreeVarExpr(var), expr))
            )
        case e.TypeCastExpr(tp=tp, arg=arg):
            return "<" + show_tp(tp) + ">" + show_expr(arg)
        case e.CheckedTypeCastExpr(
            cast_tp=(tp_from, tp_to), arg=arg, cast_spec=_
        ):
            return (
                "<"
                + show_tp(tp_from)
                + " -> "
                + show_tp(tp_to)
                + ">"
                + show_expr(arg)
            )
        case e.MultiSetExpr(expr=arr):
            return "{" + ", ".join(show_expr(el) for el in arr) + "}"
        # case e.ObjectExpr(val=elems):
        #     return "{" + ", ".join(f'{show_label(lbl)} := {show_expr(el)}'
        #                            for lbl, el in elems.items()) + "}"
        case e.ShapeExpr(shape=shape):
            return (
                "{"
                + ", ".join(
                    show_label(lbl) + " := " + show_expr(el)
                    for lbl, el in shape.items()
                )
                + "}"
            )
        case e.UnionExpr(left=left, right=right):
            return show_expr(left) + " `UNION` " + show_expr(right)
        case e.FunAppExpr(fun=fname, args=args, overloading_index=_):
            return (
                show_raw_name(fname)
                + "("
                + ", ".join(show_expr(el) for el in args)
                + ")"
            )
        case e.FreeVarExpr(var=var):
            return var
        case e.ObjectProjExpr(subject=subject, label=label):
            return show_expr(subject) + "." + label
        case e.TupleProjExpr(subject=subject, label=label):
            return show_expr(subject) + ".→" + label
        case e.LinkPropProjExpr(subject=subject, linkprop=linkprop):
            return show_expr(subject) + "@" + linkprop
        case e.WithExpr(bound=bound, next=next):
            return "with " + show_expr(bound) + ", " + show_expr(next)
        case e.DetachedExpr(expr=subject):
            return "detached " + show_expr(subject)
        case e.BackLinkExpr(subject=subject, label=label):
            return show_expr(subject) + ".<" + label
        case e.TpIntersectExpr(subject=subject, tp=tp):
            return show_expr(subject) + " [is " + show_tp(tp) + "]"
        case e.IsTpExpr(subject=subject, tp=tp):
            return show_expr(subject) + " is " + show_tp(tp)
        case e.SubqueryExpr(expr=subject):
            return "select " + show_expr(subject)
        case e.FilterOrderExpr(subject=subject, filter=filter, order=order):
            return (
                "("
                + show_expr(subject)
                + " filter "
                + show_expr(filter)
                + " order by {"
                + ", ".join(
                    [l + " => " + show_expr(o) for (l, o) in order.items()]
                )
                + "})"
            )
        case e.OffsetLimitExpr(subject=subject, offset=offset, limit=limit):
            return (
                "("
                + show_expr(subject)
                + " offset "
                + show_expr(offset)
                + " limit "
                + show_expr(limit)
                + ")"
            )
        case e.InsertExpr(name=name, new=new):
            return (
                "insert "
                + show_raw_name(name)
                + " {"
                + ", ".join(
                    [k + " := " + show_expr(n) for (k, n) in new.items()]
                )
                + "}"
            )
        case e.UpdateExpr(subject=subject, shape=shape):
            return "update " + show_expr(subject) + " " + show_expr(shape)
        case e.DeleteExpr(subject=subject):
            return "delete " + show_expr(subject)
        case e.ForExpr(bound=bound, next=next):
            return "for " + show_expr(bound) + " union " + show_expr(next)
        case e.OptionalForExpr(bound=bound, next=next):
            return (
                "for optional "
                + show_expr(bound)
                + " union "
                + show_expr(next)
            )
        case e.ShapedExprExpr(expr=subject, shape=shape):
            return show_expr(subject) + " " + show_expr(shape)
        case e.UnnamedTupleExpr(val=elems):
            return "(" + ", ".join(show_expr(el) for el in elems) + ")"
        case e.NamedTupleExpr(val=elems):
            return (
                "("
                + ", ".join(
                    f'{lbl} := {show_expr(el)}' for lbl, el in elems.items()
                )
                + ")"
            )
        case e.ArrExpr(elems=arr):
            return "[" + ", ".join(show_expr(el) for el in arr) + "]"
        case e.IfElseExpr(
            then_branch=then_branch,
            condition=condition,
            else_branch=else_branch,
        ):
            return (
                show_expr(then_branch)
                + " if "
                + show_expr(condition)
                + " else "
                + show_expr(else_branch)
            )
        case e.ConditionalDedupExpr(expr=inner):
            return "cond_dedup(" + show_expr(inner) + ")"
        case e.FreeObjectExpr():
            return "{<free>}"
        case e.ParameterExpr(name=name):
            return f"${name}"
        case e.QualifiedNameWithFilter(name=name, filter=filter):
            return (
                "with_filter("
                + show_qname(name)
                + ", "
                + show_edge_database_select_filter(filter)
                + ")"
            )
        case _:
            raise ValueError('Unimplemented', expr)


def show_arg_mod(mod: e.ParamModifier) -> str:
    match mod:
        case e.ParamSingleton():
            return "1"
        case e.ParamOptional():
            return "?"
        case e.ParamSetOf():
            return "*"
        case _:
            raise ValueError('Unimplemented', mod)


def show_arg_ret_type(tp: e.FunArgRetType) -> str:
    return (
        "["
        + (
            ", ".join(
                show_tp(arg_tp) + "^" + show_arg_mod(mod)
                for arg_tp, mod in zip(tp.args_tp, tp.args_mod)
            )
        )
        + "]"
        + " -> "
        + show_result_tp(tp.ret_tp)
    )


def show_func_defs(funcdefs: list[e.FuncDef]) -> str:
    # Hot path: funcdefs is never empty, so get first element once
    n = len(funcdefs)
    if n == 1:
        return show_arg_ret_type(funcdefs[0].tp)
    elif n > 1:
        # Avoid calling show_arg_ret_type twice
        result = show_arg_ret_type(funcdefs[0].tp)
        return result + " ..."
    else:
        raise ValueError('Unimplemented', funcdefs)


def show_constraint(constraint: e.Constraint) -> str:
    match constraint:
        case e.ExclusiveConstraint(name=name, delegated=delegated):
            # Traditional concat with ternary but with more efficient formatting
            if delegated:
                return f"exclusive({name}), delegated"
            else:
                return f"exclusive({name})"
        case _:
            raise ValueError('Unimplemented', constraint)


def show_me(me: e.ModuleEntity) -> str:
    match me:
        case e.ModuleEntityTypeDef(
            typedef=typedef, is_abstract=is_abstract, constraints=constraints
        ):
            auxiliary_parts = []
            if is_abstract:
                auxiliary_parts.append("abstract")
            if constraints:
                constraints_s = ", ".join(show_constraint(c) for c in constraints)
                auxiliary_parts.append(f"constraints = [{constraints_s}]")
            auxiliary = ""
            if auxiliary_parts:
                auxiliary = "\n    " + ", ".join(auxiliary_parts) + ", "
            base = show_tp(typedef)
            return base + auxiliary
        case e.ModuleEntityFuncDef(funcdefs=funcdefs):
            return show_func_defs(funcdefs)
        case _:
            raise ValueError('Unimplemented', me)


def show_module(dbschema: e.DBModule) -> str:
    return "\n".join(
        name + " := " + show_me(me) for name, me in dbschema.defs.items()
    )


def show_module_name(name: tuple[str, ...]) -> str:
    return "::".join(name)


def show_schema(dbschema: e.DBSchema) -> str:
    return (
        "Checked Modules:"
        + "\n".join(
            show_module_name(name) + " := { " + show_module(module) + " } "
            for name, module in dbschema.modules.items()
        )
        + "\nUnchecked Modules:\n"
        + "\n".join(
            show_module_name(name) + " := { " + show_module(module) + " } "
            for name, module in dbschema.unchecked_modules.items()
        )
    )


def show_tcctx(tcctx: e.TcCtx) -> str:
    return (
        show_schema(tcctx.schema)
        + "\n"
        + (
            "\n".join(
                name + " := " + show_result_tp(r_tp)
                for name, r_tp in tcctx.varctx.items()
            )
        )
    )


def show_visibility_marker(maker: e.Marker) -> str:
    match maker:
        case e.Visible():
            return "v"
        case e.Invisible():
            return "i"
        case _:
            raise ValueError('Unimplemented', maker)


def show_val(val: e.Val | e.ObjectVal | e.MultiSetVal) -> str:
    match val:
        case e.ScalarVal(_, _):
            return show_scalar_val(val)
        case e.ObjectVal(val=elems):
            return (
                "{"
                + ", ".join(
                    show_label(lbl)
                    + f' ({show_visibility_marker(m)}): {show_multiset_val(el)}'
                    for (lbl, (m, el)) in elems.items()
                )
                + "}"
            )
        case e.RefVal(refid=id, val=v):
            return f"ref({id})" + show_val(v)
        case e.UnnamedTupleVal(val=elems):
            return "(" + ", ".join(show_val(el) for el in elems) + ")"
        case e.NamedTupleVal(val=elems):
            return (
                "("
                + ", ".join(
                    f'{lbl} := {show_val(el)}' for lbl, el in elems.items()
                )
                + ")"
            )
        case e.ArrVal(val=arr):
            return "[" + ", ".join(show_val(el) for el in arr) + "]"
        case _:
            raise ValueError('Unimplemented', val)


def show_multiset_val(val: e.MultiSetVal) -> str:
    match val:
        case e.ResultMultiSetVal(_vals=arr):
            return (
                "(multiset val){" + ", ".join(show_val(el) for el in arr) + "}"
            )
        case _:
            raise ValueError('Unimplemented', val)


def show_ctx(ctx: e.TcCtx) -> str:
    return (
        "Schema:"
        + "\n"
        + show_schema(ctx.schema)
        + "\n"
        + "Current Module: "
        + show_module_name(ctx.current_module)
        + "\n"
        + "VarCtx:"
        + "\n"
        + (
            "\n".join(
                name + " : " + show_result_tp(r_tp)
                for name, r_tp in ctx.varctx.items()
            )
        )
        + "\n"
    )


def show(expr: Any) -> str:
    if isinstance(expr, e.Tp):  # type: ignore
        return show_tp(expr)
    elif isinstance(expr, e.Expr):  # type: ignore
        return show_expr(expr)
    elif isinstance(expr, e.Val):  # type: ignore
        return show_val(expr)
    elif isinstance(expr, e.TcCtx):
        return show_ctx(expr)
    elif isinstance(expr, e.ObjectVal):
        return show_val(expr)
    elif isinstance(expr, e.ResultTp):
        return show(expr.tp) + "^" + show_cmmode(expr.mode)
    elif isinstance(expr, e.MultiSetVal):
        return show_multiset_val(expr)
    elif isinstance(expr, list):
        return "!!!LIST([" + ", ".join(show(el) for el in expr) + "])"
    else:
        raise ValueError('Unimplemented', expr)


def p(expr: Any) -> None:
    print(show(expr))
