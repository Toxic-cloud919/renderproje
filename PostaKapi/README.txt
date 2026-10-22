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
Sunucu SMTP ile 6 haneli kod gonderir. Render Dashboard > Environment bolumunde
su gizli ortam degiskenlerini ayarla:
  SMTP_HOST
  SMTP_PORT
  SMTP_USER
  SMTP_PASSWORD
Istege bagli: SMTP_FROM

Gmail kullanirken normal Google hesap sifreni degil, Google App Password kullan.
Bu gizli degeri GitHub'a veya sohbet mesajina koyma; Render'in gizli Environment
alanina kendin gir. E-posta kodlari 10 dakika gecerli, en fazla 5 yanlis deneme
var ve yeniden kod istemek icin 1 dakika beklenir.
