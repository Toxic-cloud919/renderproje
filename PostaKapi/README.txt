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
Render ucretsiz hizmeti Gmail SMTP baglantilarini engelledigi icin Google Apps
Script e-posta koprusu eklendi. Google hesabindan e-posta yollar; ucretsiz Gmail
hesaplarinda gunde 100 alici siniri olabilir. Google limitleri degisebilir.

Ilk kurulum (bir kez):
1. https://script.google.com adresini ac ve Google hesabinda oturum ac.
2. Yeni proje olustur. Bu klasordeki GoogleMail.gs dosyasinin tum icerigini
   projedeki Code.gs dosyasina kopyala.
3. Ustteki calistirma secicisinden setupPostaKapi fonksiyonunu secip Run'a bas.
   Google izin ekranini onayla. Execution log'da yazan MAIL_APPS_SCRIPT_TOKEN
   degerini kopyala ve gizli tut.
4. Deploy > New deployment > Web app sec. Execute as: Me; Who has access: Anyone
   sec. Deploy'e bas ve /exec ile biten web app URL'sini kopyala. /dev adresini
   kullanma.
5. Render Dashboard > servis > Environment bolumune su iki degiskeni ekle:
   MAIL_APPS_SCRIPT_URL = kopyaladigin /exec URL
   MAIL_APPS_SCRIPT_TOKEN = execution log'dan kopyaladigin token
6. Save Changes / redeploy yap. E-posta ayarlari olmadan kayit veya sifre kodu
   gonderilemez. Kodlar 10 dakika gecerli; en fazla 5 yanlis deneme vardir.

Gizli degeri GitHub'a veya sohbet mesajina koyma. Script endpoint'i disariya acik
oldugu icin uzun ve rastgele bir token kullan; tokeni kaybedersen yenile ve hem
Apps Script'te hem Render Environment'ta degistir.
