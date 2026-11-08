from functools import reduce
from operator import and_

from django.db.models import CheckConstraint, Q


def en_lista(nombre, campo, valores):
    return CheckConstraint(condition=Q(**{f"{campo}__in": list(valores)}), name=nombre)


def no_negativos(*campos):
    return reduce(and_, (Q(**{f"{campo}__gte": 0}) for campo in campos))


def restriccion(nombre, condicion):
    return CheckConstraint(condition=condicion, name=nombre)
