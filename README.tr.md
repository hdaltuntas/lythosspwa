[English](README.md) | **Türkçe**

# Lythos SPWA

[![Tests](https://github.com/hdaltuntas/lythosspwa/actions/workflows/tests.yml/badge.svg)](https://github.com/hdaltuntas/lythosspwa/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/lythosspwa.svg)](https://pypi.org/project/lythosspwa/)

Tarayıcıdan sürülen palplanş duvar analizi. Konsol ya da çok ankrajlı bir duvar iki
yöntemle çözülür ve ikisi yan yana konur:

1. **Limit denge** — Coulomb / Mononobe-Okabe zemin basınçlarıyla serbest zemin desteği
   yöntemi; *gömülme derinliğini, ankraj kuvvetlerini ve iç kuvvet diyagramlarını* verir.
2. **Kiriş-yay (Winkler)** — duvarı elastoplastik zemin yayları üzerinde bir kiriş olarak,
   aşama aşama inşa ederek çözer; *imalat sırasının gerçekte doğurduğu deplasman ve
   momentleri*, yalnız çekme alan eğik ankrajlarla birlikte verir.

Her iki çözümün üzerine bir **parametrik veya güvenilirlik çalışması** istenen girdiyi —
bir aralık ya da bir dağılım olarak — tarar; duyarlılıkları, güven aralığıyla birlikte
göçme olasılığını ve güvenilirlik indeksi β'yı raporlar.

Programın tamamı — her etiket, sonuç metni, şekil ve rapor — **Türkçe ve İngilizce**
çalışır; dil çalışma sırasında değiştirilir.

Arayüz, kendi makinenizde çalışan küçük bir HTTP sunucusudur ve tarayıcıdan sürülür. Bu
sayede program uzak oturumda ya da kapsayıcı içinde de kullanılabilir — masaüstü araç
takımının isteyeceği bir ekran gerekmez — ve standart kütüphane dışında hiçbir bağımlılık
getirmez.

> [LythosFEA](https://github.com/hdaltuntas/lythos) ve
> [Lythos Kinematic](https://github.com/hdaltuntas/lythoskinematic) ile kardeştir, aynı
> mimariyi izler. Masaüstü programı **SPWA** olarak doğmuştur; bkz. [Geçmiş](#geçmiş).

## Ekran görüntüleri

| Sonuç özeti | Eğilme momenti, koyu tema |
|---|---|
| ![Sonuç özeti](screenshots/spwa_summary.png) | ![Eğilme momenti](screenshots/spwa_moment_dark.png) |

| Kiriş-yay (Winkler) | Güvenilirlik çalışması |
|---|---|
| ![Kiriş-yay](screenshots/spwa_beam_spring.png) | ![Çalışma](screenshots/spwa_study.png) |

## Kurulum ve çalıştırma

```bash
pip install lythosspwa
lythos-spwa                      # arayüzü tarayıcıda açar
```

Klondan, bilimsel yığın dışında hiçbir şey kurmadan:

```bash
pip install numpy scipy matplotlib reportlab
python main.py
```

`main.py`, kendi dizinini içe aktarma yolunun başına koyar; bu yüzden
`lythosspwa` PyPI'dan da kurulu olsa bile klondaki kod çalışır. Thonny gibi bir
düzenleyici bu durumda klasörün "`lythosspwa` kütüphane modülünü gölgelediği"
uyarısını verebilir — klondan çalıştırırken istenen düzen budur, ortada bir
sorun yoktur; kurulu kopyayı kullanmak için `lythos-spwa` komutunu başka bir
dizinden çalıştırın.

Python 3.10+ gerekir. Word raporu için `python-docx`, çalışma sonuçlarının hesap tablosu
dışa aktarımı için `openpyxl` gerekir; ikisi de isteğe bağlıdır
(`pip install "lythosspwa[docx,xlsx]"`) ve arayüz bu biçimleri yalnızca kuruluysa sunar.

## Komut satırı

```bash
lythos-spwa                                # web arayüzü (varsayılan)
lythos-spwa web --port 9000 --lang tr --no-browser
lythos-spwa example -o proje.spwa          # başlangıç proje dosyası
lythos-spwa run proje.spwa -o rapor.pdf    # analiz et, sonuçları yaz, rapor üret
lythos-spwa study proje.spwa -o ornekler.csv
```

`run` ve `study`, arayüzün kaydettiği `.spwa` dosyasının aynısını okur; tarayıcıda kurulan
bir vaka böylece başında durulmadan yeniden çalıştırılabilir.

## Neler hesaplar

### Limit denge (serbest zemin desteği)
- **Zemin basınçları:** düşey duvar için Coulomb (statik) ve Mononobe-Okabe (sismik);
  kohezyon terimi 2c√K, aktif tarafta çekme kesmesi
- **Gömülme:** uç (konsol, basitleştirilmiş yöntem) veya en alt ankraj (serbest zemin
  desteği) etrafında moment dengesi; kök bulma ile çözülür,
  `D_design = yukarı yuvarla(1.2·D_req)`
- **Ankrajlar:** ankraj başına yatay ve eksenel kuvvet, düşey bileşen
- **Diyagramlar:** net basınç, zemin ve su basınçları, kesme, moment, dönme, deplasman
- **Kontroller:** eğilme gerilmesi f_y / FS'ye karşı, deplasman H/120, H/100 ya da
  H/240'a karşı, ve gösterge niteliğinde bir düşey denge kontrolü

### Kiriş-yay (Winkler)
- Aktif ve pasif sınırlarla sınırlı elastoplastik yaylar üzerinde Euler-Bernoulli kirişi;
  sükûnet (K₀ = 1 − sin φ) durumundan başlar
- **Aşamalı imalat**, kendiliğinden kurulur: ankraj seviyesi artı kazı payına kadar kaz,
  ankrajı montajla, son seviyeye devam et; yaylar aşamalar arasında durumlarını korur
- **Ankrajlar** yalnız çekme alan yaylar olarak, `k_h = EA/(L_serbest·s)·cos²α`, kilitleme
  yüküyle
- **Yatak katsayısı** kₛ doğrudan girilir ya da Ménard-Bourdon veya Schmitt (1995) ile
  hesaplanır
- Kazıdaki su ya girildiği gibi (su altı tarama) ya da son aşamaya kadar susuzlaştırılmış

### Sismik
- Mononobe-Okabe K_AE / K_PE; su tablası altında atalet açısı θ, γdoy/γ′ ile hesaplanır
  (tutulan boşluk suyu)
- Duvar önündeki serbest suyun Westergaard hidrodinamik basıncı,
  7/8·kh·γw·√(H_w·y), kaydırıcı yük olarak uygulanır

Her iki düzeltme de kapatılabilir.

### Parametrik ve güvenilirlik çalışmaları
- **Değişkenler:** herhangi bir zemin, ankraj, geometri, yük, sismik ya da katsayı girdisi;
  aralık veya dağılım (normal, lognormal, düzgün; ortalama ve CoV) olarak
- **Örnekleme:** tek değişken taraması, tam ızgara, Latin hiperküp, Monte Carlo; korelasyonlu
  girdiler API üzerinden (`Study(..., correlation={(a, b): rho})`)
- **Sonuçlar:** Spearman sıra ve standartlaştırılmış regresyon duyarlılıkları, %95 güven
  aralığıyla göçme olasılığı ve güvenilirlik indeksi β, tornado grafikleri
- Paralel çalışır, ilerleme gösterir ve iptal edilebilir; CSV / XLSX olarak dışa aktarılır
  ve raporun 7. bölümü olur

## Raporlar

Başlıktan PDF, tek dosyalık HTML ya da Word seçip *Rapor oluştur…* düğmesine basın. Rapor;
girdileri (geometri, zemin, ankrajlar, kesit, seçenekler), limit denge sonuçlarını,
kiriş-yay sonuçlarını (kₛ tablosu, aşamalar, ankraj kuvvetleri, kontroller, LE ile
karşılaştırma), şekilleri, uyarıları ve yöntem notlarını — arayüzün o anki dilinde —
taşır. Üç biçim de tek bir yerden kurulur; bu yüzden aynı şeyi söylerler.

## Proje dosyaları (`.spwa`)

JSON. *Kaydet* girdileri ve çalışma tanımını yazar, *Aç…* geri okur. SPWA v0.1 ile
yazılmış dosyalar (yalnız ankraj derinlikleri, kₛ alanları yok) varsayılanlar
tamamlanarak açılır.

## Modüller

| dosya | içerik |
|---|---|
| `lythosspwa/analysis_engine.py` | Serbest zemin desteği analizi: Coulomb / Mononobe-Okabe basınçları, gömülme (brentq), ankraj kuvvetleri, D_req'deki diyagramlar, gerilme / deplasman / düşey kontroller |
| `lythosspwa/beam_spring.py` | Aşamalı imalatlı, yalnız çekme alan eğik ankrajlı, elastoplastik yaylar üzerinde Winkler kirişi; Ménard-Bourdon veya Schmitt'e göre kₛ |
| `lythosspwa/study.py`, `study_plots.py` | Parametrik (OAT / ızgara) ve güvenilirlik (LHS / Monte Carlo) çalışmaları: Gauss kopulalı korelasyon seçeneğiyle örnekleme, paralel koşucu, duyarlılıklar, %95 GA ile P_f ve β, CSV / XLSX dışa aktarım, şekiller |
| `lythosspwa/plotting.py`, `plot_style.py` | Matplotlib şekilleri (şema + diyagramlar, kiriş-yay 4 panel), tema duyarlı |
| `lythosspwa/report.py`, `pdf.py` | Hesap raporu: tek bir HTML kurgusu; PDF (reportlab), tek dosyalık HTML ya da DOCX olarak dışa aktarılır |
| `lythosspwa/forms.py` | Girdi şeması ve okuyucuları; arayüzün düz değerleri ile motorun yapılandırması arasında çevirir |
| `lythosspwa/summary.py` | Sonuçlar özet kartları ve metin olarak; hem tarayıcı hem komut satırı için |
| `lythosspwa/render.py` | Şekillerin PNG'ye üretimi, ekransız (Agg) |
| `lythosspwa/web/` | Yerel HTTP sunucusu, analizleri koşturan oturum ve tarayıcı arayüzü |
| `lythosspwa/config.py` | Varsayılanlar, tema, grafik paleti, çeviriler, kesit veritabanı |
| `lythosspwa/section_database.json` | Palplanş kesitlerinin I [m⁴/m] ve W [m³/m] değerleri |

## Yöntem notları

* LE: uç (konsol, basitleştirilmiş yöntem) veya en alt ankraj (serbest zemin desteği)
  etrafında moment dengesi. İç kuvvetler teorik derinlik D_req'de hesaplanır;
  imal edilen boy D_design = yukarı yuvarla(1.2·D_req). Birden çok ankrajda LE dağılımı
  yaklaşıktır — kiriş-yay sonuçları esas alınmalıdır.
* Sismik: düşey duvar için K_AE / K_PE ile Mononobe-Okabe; su tablası altında θ, γdoy/γ′
  ile; duvar önündeki serbest suya Westergaard hidrodinamik basıncı kaydırıcı yük olarak.
* Kiriş-yay: düğüm başına p = clip(p_ref ± kₛ·Δw, p_a, p_p), sükûnet başlangıcı;
  ankrajlar T = max(0, P₀·cosα/s + k_h·Δw); moment eleman eğriliğinden (EI·w″).
* Düşey kontrol (gösterge): ΣT_h·tanα, gömülü boydaki çevre sürtünmesi
  ∫(p_a + p_p)·tanδ ile karşılaştırılır; uç direnci yoktur.

## Geliştirme

```bash
pip install -e ".[dev]"
pytest -q                 # 106 test: motor, kiriş-yay, rapor, çalışma, formlar, web, paketleme
ruff check .
```

Testler; analiz çekirdeklerini kapalı form ve yayımlanmış vakalara karşı, raporu üç
biçimde de, girdi şemasını ve dosya gidiş-dönüşlerini, ve arayüzün kendisini — hem oturumu
hem HTTP katmanını — kapsar; böylece tarayıcı, tarayıcı olmadan sınanır.

PyPI'ya sürüm çıkarmak [docs/releasing.md](docs/releasing.md) içinde anlatılır;
`tools/upload_to_pypi.py` bunu terminal olmadan, bir düzenleyiciden yapar.

## Geçmiş

Lythos SPWA, masaüstü programı **SPWA**'nın (PyQt6 + Matplotlib) web uygulaması olarak
yeniden kurulmuş hâlidir: analiz çekirdekleri aynı koddur; Qt arayüzünün yerini yerel bir
sunucu ile tarayıcı sayfası, Qt tabanlı PDF yazıcısının yerini reportlab almıştır. Artık
programın hiçbir yeri ekran istemez, PyPI'dan tek komutla kurulur; özgün masaüstü sürümü
[hdaltuntas/spwa](https://github.com/hdaltuntas/spwa) adresinde durmaktadır.

## Lisans

[MIT](LICENSE) © 2025 Hasan Deniz Altuntaş

## Yazar

Hasan Deniz Altuntaş
