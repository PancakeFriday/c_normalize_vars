# converter.py

from pycparser import c_parser, c_ast
from pycparser.c_generator import CGenerator
from collections import defaultdict

def convert_code(base_code, func_code):

    gen = CGenerator()

    def find_first_function(ast):
        for ext in ast.ext:
            if isinstance(ext, c_ast.FuncDef):
                return ext
        return None

    def set_declname(decl, new_name):
        t = decl.type
        while isinstance(t, (c_ast.PtrDecl, c_ast.ArrayDecl)):
            t = t.type
        if isinstance(t, c_ast.TypeDecl):
            t.declname = new_name

    def sort_decl_blocks(block_items, keyfunc=lambda decl: decl.name):
        """
        Sort consecutive declaration blocks while preserving
        the position of all statements.
        """
        sorted_items = []
        i = 0
        n = len(block_items)

        while i < n:
            item = block_items[i]

            if isinstance(item, c_ast.Decl):
                # start of a declaration run
                start = i
                while i < n and isinstance(block_items[i], c_ast.Decl):
                    i += 1
                end = i

                decl_block = block_items[start:end]
                decl_block_sorted = sorted(decl_block, key=keyfunc)
                sorted_items.extend(decl_block_sorted)

            else:
                # regular statement: keep as-is
                sorted_items.append(item)
                i += 1

        return sorted_items

    class LocalDeclVisitor(c_ast.NodeVisitor):
        def __init__(self):
            self.locals = []

        def visit_Decl(self, node):
            # Only variable declarations inside a function
            if isinstance(node.type, (c_ast.TypeDecl, c_ast.PtrDecl, c_ast.ArrayDecl)):
                self.locals.append(node)
            self.generic_visit(node)

    class VariableUseVisitor(c_ast.NodeVisitor):
        """
        Visits every node where a variable is *used* (ID nodes),
        not declared.

        If you pass in a set of variable names, it will only
        record uses of those specific variables.
        """

        def __init__(self, filter_vars=None):
            self.uses = []                # list of (node, name, coord)
            self.filter_vars = filter_vars  # None or set of allowed var names

        def visit_ID(self, node):
            # node.name is the identifier string
            if self.filter_vars is None or node.name in self.filter_vars:
                self.uses.append((node, node.name, node.coord))

            # Continue traversal
            self.generic_visit(node)

    parser = c_parser.CParser()
    ast = parser.parse(base_code + "\n" + func_code)

    func = find_first_function(ast)

    visitor = LocalDeclVisitor()
    visitor.visit(func)

    local_names = {decl.name for decl in visitor.locals}

    # Now: find all uses of those variables
    use_visitor = VariableUseVisitor(filter_vars=local_names)
    use_visitor.visit(func)

    variable_uses = defaultdict(list)

    # use_visitor.uses now contains every usage:
    #   (node, variable_name, coord)
    for node, name, coord in use_visitor.uses:
        variable_uses[name].append(node)

    visitor = LocalDeclVisitor()
    visitor.visit(func)

    unused = []
    var_names = {}

    for var in visitor.locals:
        if var.name in variable_uses:
            ctype = gen.visit(var.type)
            replaces = [
                ("volatile ", ""),
                ("*", "p"),
                ("unsigned int", "u32"),
                ("unsigned short", "u16"),
                ("unsigned char", "u8"),
                ("unsigned long", "u32"),
                ("int", "s32"),
                ("short", "s16"),
                ("char", "s8"),
                ("long", "s32"),
                (" ", "_")
            ]
            var_name_key = ctype.lower().strip()
            for r1, r2 in replaces:
                var_name_key = var_name_key.replace(r1,r2)

            #print(var_name_key, var_names[var_name_key] if var_name_key in var_names else "-")
            if var_name_key not in var_names:
                var_names[var_name_key] = 0
            else:
                var_names[var_name_key] += 1

            new_name = f"{var_name_key}_{var_names[var_name_key]}"
            old_name = var.name

            var.name = new_name
            set_declname(var, new_name)

            for node in variable_uses[old_name]:
                node.name = new_name
        else:
            unused.append((var, "", "", var.coord.line))

    # Remove unused variables from the function body
    new_block_items = []
    for item in func.body.block_items:
        # Keep anything that is NOT a Decl
        if not isinstance(item, c_ast.Decl):
            new_block_items.append(item)
            continue

        # If it IS a Decl, keep it only if it's not unused
        if item not in [u[0] for u in unused]:
            new_block_items.append(item)

    func.body.block_items = new_block_items
    func.body.block_items = sort_decl_blocks(func.body.block_items)

    return gen.visit(func)

