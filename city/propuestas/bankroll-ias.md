# Bankroll entre IAs — apuestas con cuotas reales (moneda ficticia)

Propuesta operativa (Grok + criterio del fundador). No es la Arena genérica ni la quiniela aparcada: es **ranking de patrimonio** con cuotas de mercado reales.

## Idea en tonto

1. Cada semana (o miércoles + fin de semana) hay una **carta de eventos** con cuotas reales.
2. Cada IA apuesta moneda inventada (p. ej. 1000 al empezar la temporada).
3. Al cerrar el evento, se liquida. Se publica **quién va ganando**.

## Cadencia recomendada

| Cuándo | Qué | Quién |
|--------|-----|--------|
| **Miércoles** (o fijo semanal) | Publicar la carta: 5–10 eventos + cuotas + fuente + hora de cierre de apuestas | **1 IA “casa”** (rotar: arena / kilo / grok…) **o** el Admin pega un pantallazo/CSV |
| Hasta el cierre | Cada IA deja **su boleto** (solo el suyo) | Cada una en su turno; el Admin solo dice “boleto semana N” |
| Tras los resultados | Liquidar + actualizar ranking en la web | **1 IA “contable”** (rotar) |

El fundador **no** tiene que poner a las 4 a “buscar cuotas”. Solo:

1. Despertar a la **casa** → “publica la carta semana N”.
2. Despertar a **cada apostadora** → “lee la carta y deja tu boleto”.
3. Despertar a la **contable** → “liquida semana N”.

Opcional más comodidad: la casa usa siempre la **misma fuente** (p. ej. una casa de apuestas o API pública documentada) para no rebuscar.

## Reparto de trabajo (sin pisarse)

| Rol | Archivos / zona | Responsabilidad |
|-----|-----------------|-----------------|
| Casa | `bankroll/weeks/YYYY-Www/card.md` | Eventos, cuotas, fuente, deadline |
| Apostadora | `bankroll/weeks/YYYY-Www/bets/<ia>.json` | Solo su boleto |
| Contable | `bankroll/weeks/YYYY-Www/settlement.md` + `bankroll/leaderboard.json` | Resultados, pagos, ranking |
| Vitrina | `docs/bankroll/` | Página legible del ranking (cualquiera en relevo) |

Regla: **nadie edita el boleto de otra**. La casa no cambia cuotas tras el deadline.

## Qué hace el Admin (mínimo)

- Elegir ritmo: solo domingo / miércoles+domingo.
- Abrir 3 tipos de sesión al mes, no “todas investigando lo mismo”.
- Si quiere: pegar él la carta (cuotas) y saltarse el rol casa.

## Valor

- Web entendible: ranking + historial.
- Mide si las IAs aportan algo distinto de “siempre el favorito”.
- Compatible con “herramientas de trabajo” (plantilla de carta, script de liquidación).

## No es

- Dinero real.
- Multi-API mágica.
- Juegos abstractos que solo existen si hay partida roleada el mismo día.

— Grok · 2026-09-11
