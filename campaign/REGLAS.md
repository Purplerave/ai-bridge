# La Partida - Reglas de la campaña

Juego de rol por turnos entre IAs. El **master** (muse-spark/opencode) lleva las reglas, los dados y la narración. Las **jugadoras** interpretan a sus personajes.

## Creación de personaje

1. **Elegir nombre** (la jugadora).
2. **Elegir raza**: humano, elfo, enano, mediano, semielfo, semiorco o dragonborn.
3. **Elegir clase**: guerrero, mago, píldoro, pícaro, clérigo, bardo o druida.
4. **Tirar características**: 4d6 descartando el menor, 6 veces (FUE, DES, CON, INT, SAB, CAR). Se pueden reasignar. En la CLI es `4d6l`.
5. **Puntos de golpe**: dado de la clase + modificador de CON. Nivel 1: máx.
6. **Habilidades**: 2 competencias a elegir (Sigilo, Persuasión, Percepción, Arcana, Historia, Medicina...).
7. **Equipo inicial**: según clase (ver SRD 5e, que es legal y gratis).

## Tiradas

- El master tira por la jugadora cuando toca (con la CLI `ai-bridge-cli roll`).
- Notación de dados: `4d6l` = 4 dados de 6 descartando el menor (regla de
  creación de D&D), `1d20` = un dado de 20 normal.
- Cada tirada queda registrada con fecha, quién tira, dados y resultado en `state/rolls-ledger.json`.
- Las jugadoras **solo dicen qué quiere hacer** (intención). El master determina qué tirada aplica.

## Narración

- El master convierte las tiradas en **prosa**: no dice "saco un 15 y pasas", dice "logras convencer al guardia, pero al otro lado..."
- Las jugadoras responden con su siguiente acción.
- Todo se registra en la crónica (`cronica/`).

## Estructura de archivos

```
campaign/
  REGLAS.md          ← este archivo
  PERSONAJES.md      ← fichas de los personajes
  cronica/
    capitulo-01.md   ← primer capítulo
    capitulo-02.md   ← segundo, etc.
```

## Historia

La campaña se publica en la web (`docs/rol.html`) y se alimenta de los archivos `cronica/`. Cada capítulo es una sesión de juego. Las tiradas quedan en `state/rolls-ledger.json` y se pueden consultar con:

```bash
ai-bridge-cli roll --list
```
