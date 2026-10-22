POSTAKAPI - RENDER ICIN DOSYA DUZENI

Bu klasordeki Dockerfile, Render'daki mevcut Docker Web Service icin eklendi.
GitHub deposunda dosyalar PostaKapi klasorundeyse Render ayarlari:
- Settings > Build & Deploy > Root Directory: PostaKapi
- Dockerfile Path: Dockerfile
- Docker Context: .

Sunucuyu baslatma komutu Dockerfile tarafindan otomatik verilir.
PORT degerini Render otomatik saglar.

YERELDE CALISTIRMA:
PowerShell'de:
  cd "$env:USERPROFILE\Desktop\PostaKapi"
  python server.py
Sonra http://127.0.0.1:8000 adresini ac.

postakapi.db kullanici verisi icerebilir; GitHub'a yukleme. .gitignore ve
.dockerignore yeni yuklemelerde bu dosyayi disarida birakacak. GitHub'da daha
once yuklenmis dosyayi ayrıca depodan silmek gerekir.

VERITABANI NOTU:
Render'in ucretsiz Docker servisindeki yerel SQLite dosyasi kalici degildir;
sunucu yeniden baslayinca hesaplar ve mesajlar kaybolabilir. Kalici kullanim icin
harici/kalici bir veritabani ayarlamadan gercek kullanicilarla baslatma.

SQLITE DOSYA YOLU AYARI
Sunucu POSTAKAPI_DB_PATH ortam degiskeni verilirse SQLite'i o konumda acar.
Yerelde varsayilan dosya bu klasordeki postakapi.db'dir. Render'da kalici disk
baglarsan POSTAKAPI_DB_PATH=/var/data/postakapi.db olarak ayarlanabilir.
Ucretsiz Render hizmetinde kalici disk olmadigi icin SQLite verileri yeniden
baslatma/uyku sonrasi kaybolabilir. Gercek kullanimdan once kalici disk veya
kalici bir harici veritabani gerekir.

E-POSTA KODU AYARLARI (KAYIT VE SIFRE YENILEME)
Kodlar HTTPS ile Resend e-posta API'si kullanilarak gonderilir. Render ucretsiz
hizmetinde Gmail SMTP kullanilamaz; bu nedenle eski SMTP_HOST/SMTP_USER ayarlari
gecerli degildir.

1. Resend hesabinda bir API key olustur.
2. Gercek kullanicilara e-posta gonderebilmek icin sahip oldugun bir alan adini
   Resend'e ekleyip DNS kayitlariyla dogrula. Render adresi veya Gmail adresi
   gonderici alan adi olarak kullanilamaz.
3. Render Dashboard > servis > Environment bolumune su iki gizli degiskeni ekle:
   RESEND_API_KEY = Resend API key'in (gizli tut)
   EMAIL_FROM = PostaKapı <kod@dogruladigin-alan-adi>
4. Save Changes ile yeniden deploy et.

API key'i GitHub'a, bu repoya veya sohbet mesajina koyma. E-posta kodlari
10 dakika gecerli, en fazla 5 yanlis deneme var ve yeniden kod istemek icin
1 dakika beklenir.
