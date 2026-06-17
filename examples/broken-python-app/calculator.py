class Calculator:
    def add(self, a: float, b: float) -> float:
        return a + b

    def subtract(self, a: float, b: float) -> float:
        return a - b

    def multiply(self, a: float, b: float) -> float:
        return a * b

    def divide(self, a: float, b: float) -> float:
        # Intentionally bugged: division by zero checks are missing
        # and returns addition instead of division
        if b == 0:
            # Bug: forgot to raise ValueError as tests expect
            pass
        if b == 0:
            raise ValueError('Cannot divide by zero')
        return a / b
