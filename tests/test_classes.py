import unittest

from bparser import string_to_program
from intbase import ErrorType
from interpreterv1 import Interpreter


class TestDefinitions(unittest.TestCase):
    def setUp(self) -> None:
        self.deaf_interpreter = Interpreter(console_output=False, inp=[], trace_output=False)

    def test_no_main(self):
        brewin = string_to_program('')
        with self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin):
            error_type, _ = self.deaf_interpreter.get_error_type_and_line()
            self.assertIs(error_type, ErrorType.TYPE_ERROR)

    def test_no_method(self):
        brewin = string_to_program('(class sumn) (class main (method main () ()))')
        self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin)

    def test_out_of_order(self):
        brewin = string_to_program('''
            (class hi
                (method greet () ())
            )
            (class main
                (method main () (print "main"))
            )
            (class bye
                (method farewell () ())
            )
        ''')

        self.deaf_interpreter.reset()
        self.deaf_interpreter.run(brewin)
        output = self.deaf_interpreter.get_output()

        self.assertEqual(output[0], 'main')

    def test_method_out_of_order(self):
        brewin = string_to_program('''
            (class main
                (method main () (print greeting))
                (field greeting "hi")
            )
        ''')

        self.deaf_interpreter.reset()
        self.deaf_interpreter.run(brewin)
        output = self.deaf_interpreter.get_output()

        self.assertEqual(output[0], 'hi')

    def test_duplicate(self):
        brewin = string_to_program('''
            (class twin
                (method confuse () ())
            )
            (class twin
                (method confuse () ())
            )
            (class main
                (method main () (print "main"))
            )
        ''')
        with self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin):
            error_type, error_line = self.deaf_interpreter.get_error_type_and_line()
            self.assertIs(error_type, ErrorType.TYPE_ERROR)
            self.assertEqual(error_line, 3)


class TestFields(unittest.TestCase):
    def setUp(self) -> None:
        self.deaf_interpreter = Interpreter(console_output=False, inp=[], trace_output=False)

    def test_out_of_order(self):
        brewin = string_to_program('''
            (class main
                (method main () (print greeting))
                (field greeting "hi")
            )
        ''')

        self.deaf_interpreter.reset()
        self.deaf_interpreter.run(brewin)
        output = self.deaf_interpreter.get_output()

        self.assertEqual(output[0], 'hi')

    def test_reassignment(self):
        brewin = string_to_program('''
            (class main
                (field greeting "hi")
                (method main ()
                    (begin
                        (set greeting 14)
                        (print greeting)
                    )
                )
            )
        ''')

        self.deaf_interpreter.reset()
        self.deaf_interpreter.run(brewin)
        output = self.deaf_interpreter.get_output()

        self.assertEqual(str(output[0]), '14')

    def test_no_initial_value(self):
        brewin = string_to_program('''
            (class main
                (field blank)
                (method main () (print "main"))
            )
        ''')
        self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin)

    def test_duplicate(self):
        brewin = string_to_program('''
            (class main
                (field thing 1)
                (field thing 2)
                (method main () (print "main"))
            )
        ''')
        with self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin):
            error_type, error_line = self.deaf_interpreter.get_error_type_and_line()
            self.assertIs(error_type, ErrorType.NAME_ERROR)
            self.assertEqual(error_line, 2)


class TestMethods(unittest.TestCase):
    def setUp(self) -> None:
        self.deaf_interpreter = Interpreter(console_output=False, inp=[], trace_output=False)

    def test_missing(self):
        brewin = string_to_program('(class sumn) (class main (method main () ()))')
        self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin)

    def test_no_parameters(self):
        brewin = string_to_program('''
            (class main
                (method void)
                (method main () (print "main"))
            )
        ''')
        self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin)

    def test_no_statement(self):
        brewin = string_to_program('''
            (class main
                (method void () )
                (method main () (print "main"))
            )
        ''')
        self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin)

    def test_parameter_missing_parenthesis(self):
        brewin = string_to_program('''
            (class main
                (method void hi (return hi))
                (method main () (print (call me void "hi")))
            )
        ''')
        with self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin):
            error_type, error_line = self.deaf_interpreter.get_error_type_and_line()
            self.assertIs(error_type, ErrorType.TYPE_ERROR)
            self.assertEqual(error_line, 2)

    def test_statement_missing_parenthesis(self):
        brewin = string_to_program('''
            (class main
                (method void (hi) return hi)
                (method main () (print (call me void "hi")))
            )
        ''')
        self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin)

    def test_get_value_from_void_method(self):
        brewin = string_to_program('''
            (class main
                (method bird () ())
                (method main () (print (call me bird)))
            )
        ''')
        self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin)

    def test_get_value_from_print_method(self):
        brewin = string_to_program('''
            (class main
                (method telepath () (print ""))
                (method main () (print (call me telepath)))
            )
        ''')

        self.deaf_interpreter.reset()
        self.deaf_interpreter.run(brewin)
        output = self.deaf_interpreter.get_output()

        self.assertEqual(str(output[0]), 'None')

    def test_get_value_from_begin_method(self):
        brewin = string_to_program('''
            (class main
                (field status "it's so over")
                (method bird ()
                    (begin
                    (print "")
                    (set status "ballin")
                    )
                )
                (method main () (print (call me bird)))
            )
        ''')

        self.deaf_interpreter.reset()
        self.deaf_interpreter.run(brewin)
        output = self.deaf_interpreter.get_output()

        self.assertEqual(str(output[0]), 'None')

    def test_shadowing(self):
        brewin = string_to_program('''
            (class main
                (field x 10)
                (method bar (x) (print x))  # prints 5
                (method main () (call me bar 5))
            )
        ''')

        self.deaf_interpreter.reset()
        self.deaf_interpreter.run(brewin)
        output = self.deaf_interpreter.get_output()

        self.assertEqual(str(output[0]), '5')

    def test_duplicate(self):
        brewin = string_to_program('''
            (class main
                (method bird () (return "bush"))
                (method bird () (return "bush"))
                (method main () (print "main"))
            )
        ''')
        with self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin):
            error_type, error_line = self.deaf_interpreter.get_error_type_and_line()
            self.assertIs(error_type, ErrorType.NAME_ERROR)
            self.assertEqual(error_line, 2)

    def test_call_to_undefined(self):
        brewin = string_to_program('''
            (class main
                (method main () (call me i_dunno))
            )
        ''')
        with self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin):
            error_type, error_line = self.deaf_interpreter.get_error_type_and_line()
            self.assertIs(error_type, ErrorType.NAME_ERROR)
            self.assertEqual(error_line, 1)

    def test_too_many_arguments(self):
        brewin = string_to_program('''
            (class main
                (method const () (return 0))
                (method main () (print (call me const 1)))
            )
        ''')
        with self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin):
            error_type, error_line = self.deaf_interpreter.get_error_type_and_line()
            self.assertIs(error_type, ErrorType.TYPE_ERROR)
            self.assertEqual(error_line, 2)

    def test_too_few_arguments(self):
        brewin = string_to_program('''
            (class main
                (method ignorant (not_this nor_this) (return 0))
                (method main () (print (call me ignorant 1)))
            )
        ''')
        with self.assertRaises(RuntimeError, self.deaf_interpreter.run, brewin):
            error_type, error_line = self.deaf_interpreter.get_error_type_and_line()
            self.assertIs(error_type, ErrorType.TYPE_ERROR)
            self.assertEqual(error_line, 2)