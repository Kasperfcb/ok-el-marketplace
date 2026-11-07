## Rettet i 0.2.1 – Historikkortet indlæses automatisk

- Rettet en fejl i integrationens registrering af **Lovelace-ressourcer** på nyere Home Assistant-versioner.
- Dashboardkortet **OK El – Historik** kan nu indlæses som `custom:ok-el-history-card`, uden manuel registrering af JavaScript, når ressourcerne administreres via Home Assistants brugerflade.
- Den tilhørende JavaScript-fil serveres gennem en gyldig statisk filsti, og eksisterende dashboardressourcer bevares.
- Nye automatiske regressionstests kontrollerer registrering, opdatering og YAML-tilstand.
- **Ingen ændringer** i OK-login, historikdata, priser eller de 34 eksisterende sensorer.

**Efter opdatering:** Genstart Home Assistant og genindlæs browseren. Tilføj kortet med:

```yaml
type: custom:ok-el-history-card
```

**Manuel reserve:** Hvis ressourcetilstanden er YAML, skal `/ok-el-assets/ok-el-history-card.js?v=0.2.1` registreres som JavaScript-modul. Det nye kort er stadig ikke verificeret live på brugerens HA-installation efter denne fejlrettelse.
