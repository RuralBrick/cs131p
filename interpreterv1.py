from typing import Callable
import copy

from intbase import InterpreterBase, ErrorType
from bparser import BParser, StringWithLineNumber as SWLN


OutputFun = Callable[[str], None]
ErrorFun = Callable[[ErrorType, str, int], None]
isSWLN = lambda token: isinstance(token, SWLN)


class Barista(InterpreterBase):
    """
    Interpreter
    """
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)
        self.trace_output = trace_output
        self.output = super().output
        self.error = super().error

    def init(self):
        self.classes: dict[SWLN, Recipe] = {}

    def add_class(self, name: SWLN, body: list):
        if name in self.classes:
            self.error(ErrorType.NAME_ERROR, f"Duplicate classes: {name}")
        self.classes[name] = Recipe(name, body, self.output, self.error)

    def run(self, program: list[str]):
        well_formed, tokens = BParser.parse(program)

        if not well_formed:
            self.error(ErrorType.SYNTAX_ERROR, tokens)

        self.init()

        for class_def in tokens:
            match class_def:
                case [InterpreterBase.CLASS_DEF, name, *body] if isSWLN(name):
                    self.add_class(name, body)
                case bad:
                    self.error(ErrorType.SYNTAX_ERROR, f"Not a class: {bad}")

        # HACK
        from sys import stderr
        from pprint import pprint
        for item, cup in self.classes.items():
            print(item, file=stderr, flush=True)
            pprint(cup.fields, stderr)
            pprint(cup.methods, stderr)
        # end HACK

        try:
            cup_of_the_day = self.classes[InterpreterBase.MAIN_CLASS_DEF]
        except KeyError:
            self.error(ErrorType.TYPE_ERROR, "Main class not found")

        try:
            recommended_brew = cup_of_the_day.methods[
                InterpreterBase.MAIN_FUNC_DEF
            ]
        except KeyError:
            self.error(ErrorType.TYPE_ERROR, "Main method not found")

        try:
            recommended_brew.call(classes=self.classes)
        except ValueError:
            self.error(ErrorType.TYPE_ERROR,
                       "Main method cannot accept arguments")


Interpreter = Barista


class Recipe:
    """
    Class definition
    """
    def __init__(self, name: SWLN, body: list, output: OutputFun,
                 error: ErrorFun) -> None:
        self.name = name
        self.output = output
        self.error = error
        self.fields: dict[SWLN, Ingredient] = {}
        self.methods: dict[SWLN, Instruction] = {}

        for definition in body:
            match definition:
                case [InterpreterBase.FIELD_DEF, name, value] \
                        if isSWLN(name) and isSWLN(value):
                    self.add_field(name, value)
                case [InterpreterBase.METHOD_DEF, name, list(params),
                      statement] if isSWLN(name) and all(map(isSWLN, params)):
                    self.add_method(name, params, statement)
                case bad:
                    self.error(ErrorType.SYNTAX_ERROR,
                               f"Not a field or method: {bad}")

    def add_field(self, name: SWLN, value: SWLN):
        if name in self.fields:
            self.error(ErrorType.NAME_ERROR,
                       f"Duplicate fields in {self.name}: {name}",
                       name.line_num)
        self.fields[name] = Ingredient(value, self.error)

    def add_method(self, name: SWLN, params: list[SWLN], statement):
        if name in self.methods:
            self.error(ErrorType.NAME_ERROR,
                       f"Duplicate methods in {self.name}: {name}",
                       name.line_num)
        self.methods[name] = Instruction(name, params, statement, self,
                                         self.fields, self.output, self.error)


class Ingredient:
    """
    Field definition
    """
    def __init__(self, value: SWLN | int | str | bool | Recipe | None,
                 error: ErrorFun) -> None:
        self.error = error

        match value:
            case value if not isSWLN(value):
                from sys import stderr
                print(f"Raw value to Ingredient: {value}", file=stderr, flush=True)
                self.value = value
            case InterpreterBase.NULL_DEF:
                self.value = None
            case InterpreterBase.TRUE_DEF:
                self.value = True
            case InterpreterBase.FALSE_DEF:
                self.value = False
            case str_or_int:
                try:
                    if str_or_int[0] == '"' and str_or_int[-1] == '"':
                        self.value = str_or_int[1:-1]
                    else:
                        self.value = int(str_or_int)
                except IndexError:
                    self.error(ErrorType.SYNTAX_ERROR, "Blank value, somehow",
                               value.line_num)
                except ValueError:
                    self.error(ErrorType.SYNTAX_ERROR, "Invalid value",
                               value.line_num)

    def __repr__(self) -> str:
        match self.value:
            case True:
                return InterpreterBase.TRUE_DEF
            case False:
                return InterpreterBase.FALSE_DEF
            case None:
                return InterpreterBase.NULL_DEF
        return str(self.value)


class Instruction:
    """
    Method definition
    """
    def __init__(self, name: SWLN, params: list[SWLN], statement: list,
                 me: Recipe, scope: dict[SWLN, Ingredient], output: OutputFun,
                 error: ErrorFun) -> None:
        self.name = name
        self.formals = params
        self.statement = statement
        self.me = me
        self.scope = scope
        self.output = output
        self.error = error

    def __repr__(self) -> str:
        return f'{self.name}({self.formals}) = {str(self.statement):.32}...'

    def call(self, *args: list[Ingredient],
             classes: dict[SWLN]) -> None | Ingredient:
        """
        Throws ValueError on wrong number of arguments
        """
        parameters = {formal: actual for formal, actual
                      in zip(self.formals, args, strict=True)}

        scope = copy.deepcopy(self.scope)
        scope.update(parameters)

        return evaluate_statement(self.statement, self.me, classes, scope,
                                  self.output, self.error)


def evaluate_expression(expression, me: Recipe, classes: dict[SWLN, Recipe],
                        scope: dict[SWLN, Ingredient],
                        error: ErrorFun) -> Ingredient:
    match expression:
        case variable if isSWLN(variable) and variable in scope:
            return scope[variable]
        case const if isSWLN(const):
            return Ingredient(const, error)
        case [InterpreterBase.CALL_DEF, InterpreterBase.ME_DEF, method,
              *arguments] if isSWLN(method):
            try:
                signature_brew = me.methods[method]
            except KeyError:
                error(ErrorType.NAME_ERROR,
                      f"Could not find method: {InterpreterBase.ME_DEF}."
                      f"{method}",
                      method.line_num)
            try:
                return signature_brew.call(
                    (evaluate_expression(argument, me, classes, scope, error)
                    for argument in arguments), classes=classes
                )
            except ValueError:
                error(ErrorType.TYPE_ERROR,
                      f"Method called with wrong number of arguments: {obj}."
                      f"{method}",
                      expression[0].line_num)
        case [InterpreterBase.CALL_DEF, obj, method, *arguments] \
                if isSWLN(obj) and isSWLN(method):
            try:
                cuppa = scope[obj].value
            except KeyError:
                error(ErrorType.NAME_ERROR, f"Could not find object: {obj}",
                      obj.line_num)
            if cuppa == None:
                error(ErrorType.FAULT_ERROR,
                      f"Trying to dereference nullptr: {obj}",
                      obj.line_num)
            try:
                brew = cuppa.methods[method]
            except KeyError:
                error(ErrorType.NAME_ERROR,
                      f"Could not find method: {obj}.{method}",
                      method.line_num)
            except AttributeError:
                error(ErrorType.TYPE_ERROR, f"Not an object: {obj}",
                      obj.line_num)
            try:
                return brew.call(
                    (evaluate_expression(argument, me, classes, scope, error)
                    for argument in arguments), classes=classes
                )
            except ValueError:
                error(ErrorType.TYPE_ERROR,
                      f"Method called with wrong number of arguments: {obj}."
                      f"{method}",
                      expression[0].line_num)
        case [InterpreterBase.NEW_DEF, name] if isSWLN(name):
            try:
                cuppa = classes[name]
            except KeyError:
                error(ErrorType.TYPE_ERROR, f"Could not find class: {name}",
                      expression[0].line_num)
            return Ingredient(copy.deepcopy(cuppa), error)
        case list(expr):
            # TODO: Rest of expressions
            from sys import stderr
            print(f"Found expression: {expr}", file=stderr, flush=True)
            pass
        case bad:
            # FIXME
            error(ErrorType.TYPE_ERROR, f"Something went wrong: {bad}")


def evaluate_statement(statement, me: Recipe, classes: dict[SWLN, Recipe],
                       scope: dict[SWLN, Ingredient], output: OutputFun,
                       error: ErrorFun) -> None | Ingredient:
    match statement:
        case [InterpreterBase.BEGIN_DEF, sub_statement1, *sub_statements]:
            last_return = evaluate_statement(sub_statement1, me, classes, scope,
                                             output, error)
            for sub_statement in sub_statements:
                last_return = evaluate_statement(sub_statement, me, classes,
                                                 scope, output, error)
            return last_return
        case [InterpreterBase.CALL_DEF, InterpreterBase.ME_DEF, method,
              *arguments] if isSWLN(method):
            try:
                signature_brew = me.methods[method]
            except KeyError:
                error(ErrorType.NAME_ERROR,
                      f"Could not find method: {InterpreterBase.ME_DEF}."
                      f"{method}",
                      method.line_num)
            try:
                return signature_brew.call(
                    (evaluate_expression(argument, classes, scope, error)
                    for argument in arguments), classes=classes
                )
            except ValueError:
                error(ErrorType.TYPE_ERROR,
                      f"Method called with wrong number of arguments: {obj}."
                      f"{method}",
                      statement[0].line_num)
        case [InterpreterBase.CALL_DEF, obj, method, *arguments] \
                if isSWLN(obj) and isSWLN(method):
            try:
                cuppa = scope[obj].value
            except KeyError:
                error(ErrorType.NAME_ERROR, f"Could not find object: {obj}",
                      obj.line_num)
            if cuppa == None:
                error(ErrorType.FAULT_ERROR,
                      f"Trying to dereference nullptr: {obj}",
                      obj.line_num)
            try:
                brew = cuppa.methods[method]
            except KeyError:
                error(ErrorType.NAME_ERROR,
                      f"Could not find method: {obj}.{method}",
                      method.line_num)
            except AttributeError:
                error(ErrorType.TYPE_ERROR, f"Not an object: {obj}",
                      obj.line_num)
            try:
                return brew.call(
                    (evaluate_expression(argument, me, classes, scope, error)
                    for argument in arguments), classes=classes
                )
            except ValueError:
                error(ErrorType.TYPE_ERROR,
                      f"Method called with wrong number of arguments: {obj}."
                      f"{method}",
                      statement[0].line_num)
        case [InterpreterBase.PRINT_DEF, *arguments]:
            output(
                ''.join(
                    str(
                        evaluate_expression(argument, me, classes, scope, error)
                    )
                    for argument in arguments
                )
            )
        case list(stmt):
            # TODO: Rest of statements
            from sys import stderr
            print(f"Found statement: {str(stmt):.47}...", file=stderr, flush=True)
            pass
        case bad:
            # FIXME
            error(ErrorType.TYPE_ERROR, f"Something went wrong: {bad}")


def main():
    interpreter = Interpreter()
    script = '''
        (class main
            (field num 0)
            (field result 1)
            (method main ()
                (begin
                (print "Enter a number: ")
                (inputi num)
                (print num " factorial is " (call me factorial num))))

            (method factorial (n)
                (begin
                (set result 1)
                (while (> n 0)
                    (begin
                    (set result (* n result))
                    (set n (- n 1))))
                (return result))))
    '''
    # script = '''
    #     (class main
    #         (method main ()
    #             (print "Hello world")
    #         )
    #     )
    # '''
    interpreter.run(script.splitlines())


if __name__ == '__main__':
    main()
