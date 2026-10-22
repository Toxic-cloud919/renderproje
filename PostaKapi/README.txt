POSTAKAPI - ARKADASLIK VE SOHBET

Baslatma:
1. Baslat menusunden PowerShell ac.
2. Sunlari sirayla calistir:
   cd "$env:USERPROFILE\Desktop\PostaKapi"
   python server.py
   (python bulunamazsa: py server.py)
3. Tarayicida http://127.0.0.1:8000 adresini ac.
4. Hesap olustur. Arkadasinin da hesap acmasi gerekir.
5. Arkadasinin kayit oldugu e-posta adresini yazip istek gonder.
6. Diger hesapta gelen istegi kabul edin; sonra listeden birbirinizi secip yazisin.
7. Sunucuyu kapatmak icin PowerShell penceresinde Ctrl+C.

SQLite veritabani postakapi.db dosyasidir. Hesaplar, arkadaslik istekleri ve sohbetler
burada saklanir. Sifreler duz metin olarak tutulmaz. Sohbetler uygulama icinde gonderilir;
e-posta kutusuna mesaj gonderilmez. Yeni mesajlar yaklasik 2.5 saniyede bir kontrol edilir.

ONEMLI: 127.0.0.1 yalnizca bu bilgisayarda acilir. Farkli sehirlerdeki gercek kisilerle
kullanmak icin uygulamayi HTTPS kullanan internete acik bir sunucuya tasimamiz gerekir.
Bu ilk calisan surumde e-posta dogrulama, sifre sifirlama ve engelleme/raporlama yoktur.
