## Nyt i 0.2.0

### Overblik over alle tilgængelige OK El-målinger

- Et nyt **OK El – Historik**-dashboardkort med grafer, datotabeller og forbrugs-/prissummer for timer, dage, måneder, kvartaler og år.
- Historikken lagres **privat i Home Assistant** og kan overleve genstart. Ingen store historikfelter i sensorer eller Home Assistant Recorder.
- Hent **6–36 måneders dagsforbrug** og 0–30 aflæste dage med timeforbrug efter behov. Data importeres i baggrunden og genbruges ved efterfølgende besøg.
- Afbrudte eller delvist mislykkede imports må ikke overskrive allerede gemte aflæsninger; korrektioner og faktisk 0 kWh understøttes.
- **Dagsensorerne sorteres efter dato** med præfiks 01–07; de nyeste vises øverst.
- Alle eksisterende 34 sensor-ID'er og loginindstillinger bevares.

### Tilføj dashboardkortet

Efter Marketplace-opdatering og genstart: **Rediger dashboard → Tilføj kort → Manuel**, og indsæt:

```yaml
type: custom:ok-el-history-card
```

Hvis korttypen ikke indlæses automatisk, tilføjes ressourcen `/ok-el-assets/ok-el-history-card.js` som JavaScript-modul under Dashboard-ressourcer.

**Begrænsninger:** Det nye historikkort er ikke live-testet i Home Assistant endnu. Den eksisterende sensorintegration er bekræftet. Fakturaer og direkte Energi-dashboard-integration er endnu ikke understøttet.
