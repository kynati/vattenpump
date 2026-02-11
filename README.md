# Vattenpump-projekt 🚿

Ett projekt för att styra en vattenpump med sensorer via en webbgränssnitt eller GUI.

## Funktioner
- **Webbgränssnitt** - Kontrollera pumpen via en hemsida (app.py)
- **Desktop GUI** - Lokal kontroll med Tkinter-gränssnitt (main.py)
- **Sensorer** - Temperatur (DS18B20), fukt (ADS1115) och flödesläsning (FLOW_PIN)
- **Simuleringsläge** - Testa utan Raspberry Pi-hårdvara

## Krav
- Python 3.7+
- Flask (för webbservern)
- RPi.GPIO (för Raspberry Pi)

## Installation

1. Klona repot:
```bash
git clone https://github.com/kynati/vattenpump.git
cd vattenpump
```

2. Installera beroenden:
```bash
pip install -r requirements.txt
```

3. Kör programmet:

**Webbversion:**
```bash
python app.py
```
Öppna sedan: http://localhost:5000

**Desktop-version:**
```bash
python main.py
```

## Systemkrav
- Raspberry Pi 4 (eller senare)
- GPIO-kompatibel hårdvara
- Python 3.7+

## Utvecklad av
kynati

## Licens
MIT
