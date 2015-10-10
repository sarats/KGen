# kgen_genfiles.py

from kgen_utils import KGName, Config, ProgramException, pack_innamepath, match_namepath
from kgen_state import State
from api import walk
from typedecl_statements import TypeDeclarationStatement
from base_classes import BeginStatement
from block_statements import BeginSource, Module, Type
from statements import Assignment, Use

dtypes_found = []

def append_tkdpat(loctype, var, stmt, tkdpatlist, mod_depends=None, component=True):
    from Fortran2003 import Entity_Decl

    if var.is_pointer() or var.is_allocatable() or var.is_array() or stmt.is_derived():
        varpointer = var.is_pointer()
        varalloc = var.is_allocatable()

        if var.is_array():
            vardim = var.rank
            if var.is_explicit_shape_array():
                vardim *= -1
        else: vardim = 0

        if stmt.is_derived():
            vartype = stmt.name
            varkind = ''
            res_stmts = stmt.get_res_stmts(stmt.name)
            if res_stmts is None or len(res_stmts)==0:
                dtype = None
            else:
                dtype = res_stmts[-1]
        else:
            vartype = stmt.__class__.__name__.lower()
            varkind = stmt.get_kind()
            dtype = None

        if len(tkdpatlist)==0 or \
            all( loctype!=tkdpat_loctype or vartype!=tkdpat_type or varkind!=tkdpat_kind or vardim!=tkdpat_dim or \
                varpointer!=tkdpat_pointer or varalloc!=tkdpat_alloc or dtype!=tkdpat_dtype \
                for tkdpat_loctype, tkdpat_type, tkdpat_kind, tkdpat_dim, tkdpat_pointer, tkdpat_alloc, tkdpat_dtype in tkdpatlist):
            tkdpatlist.append( (loctype, vartype, varkind, vardim, varpointer, varalloc, dtype) )

        # add tkdpat from derived type components
        if dtype:
            if isinstance(dtype, Use):
                if (not mod_depends is None) and (not dtype.name.lower() in mod_depends):
                    mod_depends.append(dtype.name.lower()) 
            elif component and pack_innamepath(dtype, dtype.name) not in dtypes_found:
                dtypes_found.append(pack_innamepath(dtype, dtype.name))

                for comp in dtype.content:
                    if isinstance(comp, TypeDeclarationStatement):
                        for decl in comp.entity_decls:
                            entity = Entity_Decl(decl)
                            varname = entity.items[0].string.lower()
                            var = dtype.a.variables[varname]
                            append_tkdpat(loctype, var, comp, tkdpatlist)

def process_spec_stmts(parent, is_callsite):
    from statements import Access, Allocatable, Asynchronous, Bind, Common, Data, Dimension, Equivalence, External, Intent, \
        Intrinsic, Namelist, Optional, Pointer, Protected, Save, Target, Volatile, Value, Contains
    from typedecl_statements import Implicit

    for spec_stmt in parent.spec_stmts:
        if isinstance(spec_stmt, Access):
            # add access stmt without items
            if hasattr(parent, 'geninfo') and not hasattr(spec_stmt, 'geninfo') and \
                len(spec_stmt.items)==0:
                spec_stmt.geninfo = {}
        elif isinstance(spec_stmt, Allocatable):
            pass
        elif isinstance(spec_stmt, Asynchronous):
            pass
        elif isinstance(spec_stmt, Bind):
            pass
        elif isinstance(spec_stmt, Common):
            pass
        elif isinstance(spec_stmt, Data):
            pass
        elif isinstance(spec_stmt, Dimension):
            pass
        elif isinstance(spec_stmt, Equivalence):
            pass
        elif isinstance(spec_stmt, External):
            pass
        elif isinstance(spec_stmt, Intent):
            pass
        elif isinstance(spec_stmt, Intrinsic):
            pass
        elif isinstance(spec_stmt, Namelist):
            pass
        elif isinstance(spec_stmt, Optional):
            pass
        elif isinstance(spec_stmt, Pointer):
            pass
        elif isinstance(spec_stmt, Protected):
            pass
        elif isinstance(spec_stmt, Save):
            pass
        elif isinstance(spec_stmt, Target):
            pass
        elif isinstance(spec_stmt, Volatile):
            pass
        elif isinstance(spec_stmt, Value):
            pass
        elif isinstance(spec_stmt, Contains):
            if hasattr(parent, 'geninfo') and not hasattr(spec_stmt, 'geninfo'):
                spec_stmt.geninfo = {}
        elif isinstance(spec_stmt, Implicit):
            if hasattr(parent, 'geninfo') and not hasattr(spec_stmt, 'geninfo'):
                spec_stmt.geninfo = {}

def preprocess_generation_info(tree):
    # mark high level stmts and process spec. stmts
    for stmt, depth in walk(tree, -1):
        # mark end statements and higher level block
        if hasattr(stmt, 'unknowns') or hasattr(stmt, 'geninfo'):
            if not hasattr(stmt, 'geninfo'): stmt.geninfo = {}
            if isinstance(stmt, BeginStatement) and not hasattr(stmt.content[-1], 'geninfo'):
                stmt.content[-1].geninfo = {}
            ancestors = stmt.ancestors()
            for ancestor in ancestors:
                if not hasattr(ancestor, 'geninfo'):
                    ancestor.geninfo = {}
                if not hasattr(ancestor.content[-1], 'geninfo'):
                    ancestor.content[-1].geninfo = {}
                if hasattr(ancestor, 'spec_stmts'):
                    process_spec_stmts(ancestor, True)

        # process sepc. stmts
        if hasattr(stmt, 'spec_stmts'):
            process_spec_stmts(stmt, True)

def mark_callsite_generation_info():
    """ Mark each statement objects with kernel generation information """

    from Fortran2003 import Part_Ref, Assignment_Stmt

    cs_tree = State.topblock['file'].tree
    actual_args = State.callsite['actual_arg']['names']
    dummy_args = [ n.firstpartname() for n in State.parentblock['dummy_arg']['names'] ]


    preprocess_generation_info(cs_tree)

    # mark input state in callsite
    for stmt, depth in walk(cs_tree, -1):

        # collect use stmt usage
        if hasattr(stmt, 'unknowns') and len(stmt.unknowns)>0:
            for unknown, res in stmt.unknowns.iteritems():
                cur_name = unknown.firstpartname()
                if res.res_stmts and len(res.res_stmts)>0:
                    for res_stmt in res.res_stmts:
                        if isinstance(res_stmt, Use):
                            if cur_name not in res_stmt.used:
                                res_stmt.used.append(cur_name)
                            for rename, orig in res_stmt.renames:
                                if cur_name==rename:
                                    cur_name = orig
                                    break

        # if marked
        if hasattr(stmt, 'geninfo') and isinstance(stmt, TypeDeclarationStatement) and \
            stmt.geninfo.has_key(KGName):
            used = []
            for kgname in stmt.geninfo[KGName]:
                if kgname.firstpartname() in used: continue
                else: used.append(kgname.firstpartname())
                # if in topblock
                if stmt.parent is State.topblock['stmt']:
                    var = stmt.parent.a.variables[kgname.firstpartname()]
                    if not var.is_parameter():
                        State.topblock['extern']['names'].append(kgname)
                        State.topblock['extern']['typedecl_stmt'][kgname] = stmt
                        append_tkdpat(State.TB_EXTERN, var, stmt, State.topblock['extern']['tkdpat'], \
                            State.topblock['mod_rw_var_depends'])
                        if State.kernel['stmt'] in kgname.stmt.ancestors():
                            State.parentblock['output']['names'].append(kgname)
                            State.parentblock['output']['typedecl_stmt'][kgname] = stmt
                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['inout']['tkdpat'], State.topblock['mod_rw_var_depends'])
                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['output']['tkdpat'])
                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['writesubr']['tkdpat'])
                # else if in parent block
                elif stmt.parent is State.parentblock['stmt']:
                    #  kernel driver
                    if kgname.firstpartname() in dummy_args:
                        idx = dummy_args.index(kgname.firstpartname())
                        darg = State.parentblock['dummy_arg']['names'][idx]
                        var = stmt.parent.a.variables[kgname.firstpartname()]
                        if darg in State.parentblock['dummy_arg']['in_names'] or \
                            State.parentblock['dummy_arg']['inout_names']:
                            State.kernel_driver['input']['names'].append(kgname)
                            State.kernel_driver['input']['typedecl_stmt'][kgname] = stmt
                            append_tkdpat(State.KD_INPUT, var, stmt, State.kernel_driver['input']['tkdpat'], \
                                State.kernel_driver['mod_rw_var_depends'], component=False)
                            append_tkdpat(State.KD_INPUT, var, stmt, State.parentblock['writesubr']['tkdpat'], \
                                State.topblock['mod_rw_var_depends'])

                    # save all variables as input except kernel_driver vars
                    var = stmt.parent.a.variables[kgname.firstpartname()]
                    if not kgname in State.kernel_driver['input']['names'] and \
                        not var.is_parameter():
                        State.parentblock['input']['names'].append(kgname)
                        State.parentblock['input']['typedecl_stmt'][kgname] = stmt
                        append_tkdpat(State.PB_INPUT, var, stmt, State.parentblock['inout']['tkdpat'], State.topblock['mod_rw_var_depends'])
                        append_tkdpat(State.PB_INPUT, var, stmt, State.parentblock['writesubr']['tkdpat'])

                    # check with actual and dummy
                    #if kgname.firstpartname() in actual_args:
                    if actual_args and actual_args.has_firstpartname(kgname.firstpartname()):
                        idx = actual_args.index_firstpartname(kgname.firstpartname())
                        aarg = actual_args.get_arg(idx)
                        if aarg.is_keyword:
                            dnames = [ n.firstpartname() for n in State.kernel['dummy_arg']['names']]
                            if aarg.keyword in dnames:
                                for i, dname in enumerate(dnames):
                                    if dname==aarg.keyword:
                                        idx = i
                                        break
                            else:
                                raise ProgramException('Keyword dummy argument is not found: %s'%aarg.keyword)
                        darg = State.kernel['dummy_arg']['names'][idx]
                        if darg in State.kernel['dummy_arg']['in_names']:
                            pass
                        elif darg in State.kernel['dummy_arg']['out_names'] or \
                            darg in State.kernel['dummy_arg']['inout_names']:
                            State.parentblock['output']['names'].append(kgname)
                            State.parentblock['output']['typedecl_stmt'][kgname] = stmt
                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['inout']['tkdpat'], State.topblock['mod_rw_var_depends'])
                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['output']['tkdpat']) 
                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['writesubr']['tkdpat'])
                        else: raise ProgramException('No intent: %s,%s'% \
                            (kgname.firstpartname(), darg.firstpartname()))
                    # check if org in kernel
                    elif State.kernel['stmt'] in kgname.stmt.ancestors():
                        State.parentblock['output']['names'].append(kgname)
                        State.parentblock['output']['typedecl_stmt'][kgname] = stmt
                        append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['inout']['tkdpat'], State.topblock['mod_rw_var_depends'])
                        append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['output']['tkdpat'])
                        append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['writesubr']['tkdpat'])
                    # check if org in callsite stmt
                    elif kgname.stmt is State.callsite['stmt'] and isinstance(State.callsite['expr'], Part_Ref):
                        expr = State.callsite['expr']
                        if hasattr(expr, 'parent') and isinstance(expr.parent, Assignment_Stmt):
                            if expr.parent.items[0].tofortran().lower().startswith(kgname.firstpartname()):
                                State.parentblock['output']['names'].append(kgname)
                                State.parentblock['output']['typedecl_stmt'][kgname] = stmt
                                append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['inout']['tkdpat'], State.topblock['mod_rw_var_depends'])
                                append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['output']['tkdpat'])
                                append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['writesubr']['tkdpat'])
                        else:
                            raise ProgramException("Only assignment statement is allowed for Function callsite yet.")

#                    elif kgname.stmt is State.callsite['stmt'] and isinstance(kgname.stmt, Assignment):
#                        if kgname.stmt.variable.startswith(kgname.firstpartname()):
#                            State.parentblock['output']['names'].append(kgname)
#                            State.parentblock['output']['typedecl_stmt'][kgname] = stmt
#                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['inout']['tkdpat'], State.topblock['mod_rw_var_depends'])
#                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['output']['tkdpat'])
#                            append_tkdpat(State.PB_OUTPUT, var, stmt, State.parentblock['writesubr']['tkdpat'])


        elif hasattr(stmt, 'geninfo') and isinstance(stmt, Type) and stmt.geninfo.has_key(KGName):
            stmt_parent = stmt.ancestors()[-1]
            if stmt_parent is State.topblock['stmt']:
                State.topblock['dtype'].append(stmt)
                for varname, var in stmt.a.variables.iteritems():
                    remove = False
                    if Config.exclude.has_key('namepath'):
                        for pattern, actions in Config.exclude['namepath'].iteritems():
                            namepath = pack_innamepath(var.parent, var.parent.name) 
                            #if var.parent.name=='file_desc_t':import pdb; pdb.set_trace()
                            if match_namepath(pattern, namepath) and 'remove' in actions:
                                remove = True
                                if not hasattr(var.parent, 'nosave_state_names'):
                                    var.parent.nosave_state_names = []
                                var.parent.nosave_state_names.append(var.parent.name)

                                if not hasattr(var.parent, 'exclude_names'): var.parent.exclude_names = {}
                                if var.parent.exclude_names.has_key(var.parent.name):
                                    var.parent.exclude_names[var.parent.name].append('comment')
                                else:
                                    var.parent.exclude_names[var.parent.name] = ['comment']

                                break

                    if not remove:
                        append_tkdpat(State.DT_CALLMODULE, var, var.parent, State.topblock['extern']['tkdpat'], \
                            State.topblock['mod_rw_var_depends'])

            elif stmt_parent is State.parentblock['stmt']:
                State.parentblock['dtype'].append(stmt)
                for varname, var in stmt.a.variables.iteritems():
                    remove = False
                    if Config.exclude.has_key('namepath'):
                        for pattern, actions in Config.exclude['namepath'].iteritems():
                            namepath = pack_innamepath(var.parent, var.parent.name) 
                            #if var.parent.name=='file_desc_t':import pdb; pdb.set_trace()
                            if match_namepath(pattern, namepath) and 'remove' in actions:
                                remove = True
                                if not hasattr(var.parent, 'nosave_state_names'):
                                    var.parent.nosave_state_names = []
                                var.parent.nosave_state_names.append(var.parent.name)

                                if not hasattr(var.parent, 'exclude_names'): var.parent.exclude_names = {}
                                if var.parent.exclude_names.has_key(var.parent.name):
                                    var.parent.exclude_names[var.parent.name].append('comment')
                                else:
                                    var.parent.exclude_names[var.parent.name] = ['comment']

                                break

                    if not remove:
                        append_tkdpat(State.DT_CALLPARENT, var, var.parent, State.parentblock['writesubr']['tkdpat'], \
                            State.parentblock['mod_rw_var_depends'])

def mark_programunits_generation_info():
    """ Mark each statement objects with kernel generation information """

    processed_files = []

    # mark info for all files other than callsite file
    for filepath, (srcfile, mods_used, units_used) in State.depfiles.iteritems():
        if filepath!=State.topblock['path']:
            # mark high level stmts and process spec. stmts
            processed_files.append(filepath)

            preprocess_generation_info(srcfile.tree)

            for stmt, depth in walk(srcfile.tree, -1):
                # collect use stmt usage
                if hasattr(stmt, 'unknowns') and len(stmt.unknowns)>0:
                    for unknown, res in stmt.unknowns.iteritems():
                        cur_name = unknown.firstpartname()
                        if res.res_stmts and len(res.res_stmts)>0:
                            for res_stmt in res.res_stmts:
                                if isinstance(res_stmt, Use):
                                    if cur_name not in res_stmt.used:
                                        res_stmt.used.append(cur_name)
                                    for rename, orig in res_stmt.renames:
                                        if cur_name==rename:
                                            cur_name = orig
                                            break

                if isinstance(stmt.parent, Module):
                    if hasattr(stmt, 'geninfo') and isinstance(stmt, TypeDeclarationStatement) and \
                        stmt.geninfo.has_key(KGName):
                        mod_name = stmt.parent.name
                        used = []
                        for kgname in stmt.geninfo[KGName]:
                            if kgname.firstpartname() in used:continue
                            else: used.append(kgname.firstpartname())

                            var = stmt.parent.a.variables[kgname.firstpartname()]
                            if not var.is_parameter():
                                srcfile.used4genstate = True
                                State.modules[mod_name]['extern']['names'].append(kgname)
                                State.modules[mod_name]['extern']['typedecl_stmt'][kgname] = stmt
                                append_tkdpat(State.MOD_EXTERN, var, stmt, State.modules[mod_name]['extern']['tkdpat'], \
                                    State.modules[mod_name]['mod_rw_var_depends'])

                    elif hasattr(stmt, 'geninfo') and isinstance(stmt, Type) and stmt.geninfo.has_key(KGName):
                        mod_name = stmt.parent.name
                        srcfile.used4genstate = True
                        State.modules[mod_name]['dtype'].append(stmt)

                        for varname, var in stmt.a.variables.iteritems():
                            remove = False
                            if Config.exclude.has_key('namepath'):
                                for pattern, actions in Config.exclude['namepath'].iteritems():
                                    namepath = pack_innamepath(var.parent, var.parent.name) 
                                    if match_namepath(pattern, namepath) and 'remove' in actions:
                                        remove = True
                                        if not hasattr(var.parent, 'nosave_state_names'):
                                            var.parent.nosave_state_names = []
                                        var.parent.nosave_state_names.append(var.parent.name)

                                        if not hasattr(var.parent, 'exclude_names'): var.parent.exclude_names = {}
                                        if var.parent.exclude_names.has_key(var.parent.name):
                                            var.parent.exclude_names[var.parent.name].append('comment')
                                        else:
                                            var.parent.exclude_names[var.parent.name] = ['comment']

                                        break

                            if not remove:
                                append_tkdpat(State.DT_MODULE, var, var.parent, State.modules[mod_name]['extern']['tkdpat'], \
                                    State.modules[mod_name]['mod_rw_var_depends'])

                elif any( any(stmt==unit for unit in units) for units in State.program_units.values() ):
                    pass

def mark_generation_info():
    """ Mark each statement objects with kernel generation information """

    mark_callsite_generation_info()
    mark_programunits_generation_info()

    #if State.callsite['actual_arg']['names']:
    #    State.callsite['actual_arg']['names'].sort()
    State.callsite['actual_arg']['in_names'].sort()
    State.callsite['actual_arg']['out_names'].sort()
    State.callsite['actual_arg']['inout_names'].sort()
    State.parentblock['dummy_arg']['names'].sort()
    State.parentblock['dummy_arg']['in_names'].sort()
    State.parentblock['dummy_arg']['out_names'].sort()
    State.parentblock['dummy_arg']['inout_names'].sort()
    State.parentblock['input']['names'].sort()
    State.parentblock['output']['names'].sort()
    State.topblock['extern']['names'].sort()
    #State.kernel['dummy_arg']['names'].sort()
    State.kernel['dummy_arg']['in_names'].sort()
    State.kernel['dummy_arg']['out_names'].sort()
    State.kernel['dummy_arg']['inout_names'].sort()
    State.kernel_driver['input']['names'].sort()
    for modname, modattrs in State.modules.iteritems():
        modattrs['extern']['names'].sort()

    State.state = State.GENINFO_MARKED
