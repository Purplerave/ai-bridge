"""
Desafío 01: Búsqueda Binaria con Bug Off-By-One.

Función que busca la posición de 'target' en una lista ordenada 'arr'.
Debe retornar el índice si existe, o -1 si no existe.
"""

def binary_search(arr, target):
    left = 0
    right = len(arr) - 1

    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1
