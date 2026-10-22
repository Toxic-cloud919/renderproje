from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import hashlib, hmac, json, os, re, secrets, sqlite3, time

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("POSTAKAPI_DB_PATH", str(ROOT / "postakapi.db")))
HOST = os.environ.get("HOST", "0.0.0.0" if "PORT" in os.environ else "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
ITERATIONS = 600_000
SESSION_SECONDS = 14 * 24 * 60 * 60
CODE_SECONDS, RESEND_SECONDS, MAX_CODE_TRIES = 600, 60, 5

def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def initialize_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          email TEXT NOT NULL COLLATE NOCASE UNIQUE,
          password_hash TEXT NOT NULL, password_salt TEXT NOT NULL, created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS friend_requests (
          id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted')),
          created_at INTEGER NOT NULL, UNIQUE(sender_id, receiver_id), CHECK(sender_id != receiver_id)
        );
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          body TEXT NOT NULL CHECK(length(body) <= 2000), created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS messages_pair_idx ON messages(sender_id, receiver_id, id);
        CREATE TABLE IF NOT EXISTS email_codes (
          email TEXT NOT NULL, purpose TEXT NOT NULL CHECK(purpose IN ('register','reset')),
          code_hash TEXT NOT NULL, code_salt TEXT NOT NULL, payload TEXT NOT NULL,
          created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(email, purpose)
        );
        """)

def pw_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex()

def token_hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()

def email_code_hash(code, salt):
    return hashlib.sha256((salt + code).encode("utf-8")).hexdigest()

def mail_ready():
    apps_script_ready = bool(os.environ.get("MAIL_APPS_SCRIPT_URL") and os.environ.get("MAIL_APPS_SCRIPT_TOKEN"))
    resend_ready = bool(os.environ.get("RESEND_API_KEY") and os.environ.get("EMAIL_FROM"))
    return apps_script_ready or resend_ready

def send_email_code(email, code, purpose):
    if not mail_ready():
        raise RuntimeError("Email API settings missing")
    purpose_text = "hesap oluşturma" if purpose == "register" else "şifre yenileme"
    message = f"PostaKapı {purpose_text} kodun: {code}\n\nKod 10 dakika geçerlidir. Bu isteği sen yapmadıysan bu e-postayı yok say."
    apps_script_url = os.environ.get("MAIL_APPS_SCRIPT_URL")
    apps_script_token = os.environ.get("MAIL_APPS_SCRIPT_TOKEN")
    if apps_script_url and apps_script_token:
        payload = json.dumps({
            "token": apps_script_token,
            "to": email,
            "subject": f"PostaKapı {purpose_text} kodun",
            "text": message
        }).encode("utf-8")
        request = Request(apps_script_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                if response.status != 200 or result.get("ok") is not True:
                    raise RuntimeError("Apps Script email request failed")
        except (HTTPError, URLError, ValueError) as exc:
            raise RuntimeError("Apps Script email request failed") from None
        return
    payload = json.dumps({
        "from": os.environ["EMAIL_FROM"],
        "to": [email],
        "subject": f"PostaKapı {purpose_text} kodun",
        "text": message
    }).encode("utf-8")
    request = Request("https://api.resend.com/emails", data=payload, headers={
        "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
        "Content-Type": "application/json"
    }, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"Email API returned HTTP {response.status}")
    except HTTPError as exc:
        raise RuntimeError(f"Email API returned HTTP {exc.code}") from None
    except URLError as exc:
        raise RuntimeError("Email API connection failed") from None

def issue_email_code(email, purpose, payload):
    now = int(time.time())
    with connect_db() as db:
        prev = db.execute("SELECT created_at FROM email_codes WHERE email=? AND purpose=?", (email, purpose)).fetchone()
        if prev and now - prev["created_at"] < RESEND_SECONDS:
            return False, "Yeni kod istemeden önce bir dakika bekle."
    code, salt = f"{secrets.randbelow(1_000_000):06d}", secrets.token_hex(16)
    digest = email_code_hash(code, salt)
    with connect_db() as db:
        db.execute("""INSERT INTO email_codes(email,purpose,code_hash,code_salt,payload,created_at,expires_at,attempts)
          VALUES(?,?,?,?,?,?,?,0) ON CONFLICT(email,purpose) DO UPDATE SET
          code_hash=excluded.code_hash,code_salt=excluded.code_salt,payload=excluded.payload,
          created_at=excluded.created_at,expires_at=excluded.expires_at,attempts=0""",
          (email,purpose,digest,salt,json.dumps(payload),now,now+CODE_SECONDS))
    try:
        send_email_code(email, code, purpose)
    except Exception as exc:
        with connect_db() as db:
            db.execute("DELETE FROM email_codes WHERE email=? AND purpose=? AND code_hash=?", (email,purpose,digest))
        print(f"[PostaKapi] Email delivery failed: {type(exc).__name__}")
        return False, "E-posta gönderilemedi. Sunucu e-posta ayarlarını kontrol etmek gerekiyor."
    return True, "Doğrulama kodu e-posta adresine gönderildi. Kod 10 dakika geçerli."

def check_code(db, email, purpose, code):
    row = db.execute("SELECT * FROM email_codes WHERE email=? AND purpose=?", (email,purpose)).fetchone()
    now = int(time.time())
    if not row:
        return None, "Önce e-posta kodu iste."
    if row["expires_at"] < now:
        db.execute("DELETE FROM email_codes WHERE email=? AND purpose=?", (email,purpose))
        return None, "Kodun süresi dolmuş. Yeni kod iste."
    if row["attempts"] >= MAX_CODE_TRIES:
        db.execute("DELETE FROM email_codes WHERE email=? AND purpose=?", (email,purpose))
        return None, "Çok fazla yanlış deneme oldu. Yeni kod iste."
    if not hmac.compare_digest(email_code_hash(code,row["code_salt"]),row["code_hash"]):
        tries = row["attempts"] + 1
        if tries >= MAX_CODE_TRIES:
            db.execute("DELETE FROM email_codes WHERE email=? AND purpose=?", (email,purpose))
            return None, "Kod hatalı. Deneme sınırı doldu; yeni kod iste."
        db.execute("UPDATE email_codes SET attempts=? WHERE email=? AND purpose=?", (tries,email,purpose))
        return None, f"Kod hatalı. Kalan deneme: {MAX_CODE_TRIES-tries}."
    return row, None

class Handler(BaseHTTPRequestHandler):
    server_version = "PostaKapiLocal/1.0"
    def json_out(self, status, data, extra=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        if extra:
            for key,value in extra.items(): self.send_header(key,value)
        self.end_headers(); self.wfile.write(body)
    def read_json(self):
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 1 <= size <= 12000: return None
            return json.loads(self.rfile.read(size))
        except (ValueError,json.JSONDecodeError): return None
    def current_user(self):
        token=""
        for part in self.headers.get("Cookie","").split(";"):
            key,_,value=part.strip().partition("=")
            if key=="pk_session": token=value
        if len(token)!=64: return None
        with connect_db() as db:
            row=db.execute("SELECT u.id,u.name,u.email FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?",(token_hash(token),int(time.time()))).fetchone()
        return dict(row) if row else None
    def require_user(self):
        user=self.current_user()
        if not user: self.json_out(401,{"error":"Lütfen önce giriş yap."})
        return user
    def issue_session(self, uid):
        token=secrets.token_hex(32)
        with connect_db() as db:
            db.execute("DELETE FROM sessions WHERE expires_at<=?",(int(time.time()),))
            db.execute("INSERT INTO sessions VALUES(?,?,?)",(token_hash(token),uid,int(time.time())+SESSION_SECONDS))
        return {"Set-Cookie":f"pk_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}"}
    def do_GET(self):
        parsed=urlparse(self.path); route=parsed.path
        files={"/":"index.html","/style.css":"style.css","/app.js":"app.js"}
        if route in files: return self.static(files[route],{"/":"text/html; charset=utf-8","/style.css":"text/css; charset=utf-8","/app.js":"text/javascript; charset=utf-8"}[route])
        if route=="/api/me": return self.json_out(200,{"user":self.current_user()})
        user=self.require_user()
        if not user: return
        if route=="/api/friends":
            with connect_db() as db:
                friends=db.execute("SELECT u.id,u.name,u.email FROM friend_requests f JOIN users u ON u.id=CASE WHEN f.sender_id=? THEN f.receiver_id ELSE f.sender_id END WHERE f.status='accepted' AND (f.sender_id=? OR f.receiver_id=?) ORDER BY u.name COLLATE NOCASE",(user["id"],user["id"],user["id"])).fetchall()
                incoming=db.execute("SELECT f.id,u.name,u.email FROM friend_requests f JOIN users u ON u.id=f.sender_id WHERE f.receiver_id=? AND f.status='pending' ORDER BY f.created_at",(user["id"],)).fetchall()
                outgoing=db.execute("SELECT u.email FROM friend_requests f JOIN users u ON u.id=f.receiver_id WHERE f.sender_id=? AND f.status='pending'",(user["id"],)).fetchall()
            return self.json_out(200,{"friends":[dict(x) for x in friends],"incoming":[dict(x) for x in incoming],"outgoing":[x["email"] for x in outgoing]})
        if route=="/api/messages":
            try: friend_id=int(parse_qs(parsed.query).get("friend",[""])[0])
            except ValueError: return self.json_out(400,{"error":"Arkadaş seçilmedi."})
            with connect_db() as db:
                allowed=db.execute("SELECT 1 FROM friend_requests WHERE status='accepted' AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?))",(user["id"],friend_id,friend_id,user["id"])).fetchone()
                if not allowed: return self.json_out(403,{"error":"Mesajlaşmak için arkadaş isteği kabul edilmiş olmalı."})
                rows=db.execute("SELECT id,sender_id,receiver_id,body,created_at FROM messages WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?) ORDER BY id DESC LIMIT 100",(user["id"],friend_id,friend_id,user["id"])).fetchall()
            return self.json_out(200,{"messages":[dict(x) for x in reversed(rows)]})
        return self.json_out(404,{"error":"Bulunamadı."})
    def static(self, filename, mime):
        try: body=(ROOT/filename).read_bytes()
        except OSError: return self.json_out(500,{"error":"Site dosyası bulunamadı."})
        self.send_response(200); self.send_header("Content-Type",mime); self.send_header("Content-Length",str(len(body))); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        route=urlparse(self.path).path; data=self.read_json()
        if data is None: return self.json_out(400,{"error":"Form okunamadı."})
        public={"/api/register":self.register,"/api/verify-registration":self.verify_registration,"/api/login":self.login,"/api/forgot-password":self.forgot_password,"/api/reset-password":self.reset_password,"/api/logout":self.logout}
        if route in public: return public[route](data)
        user=self.require_user()
        if not user: return
        if route=="/api/friend-requests": return self.send_friend_request(user,data)
        if route.startswith("/api/friend-requests/") and route.endswith("/accept"):
            try: rid=int(route.split("/")[3])
            except (ValueError,IndexError): return self.json_out(400,{"error":"İstek numarası hatalı."})
            with connect_db() as db:
                cur=db.execute("UPDATE friend_requests SET status='accepted' WHERE id=? AND receiver_id=? AND status='pending'",(rid,user["id"]))
                if not cur.rowcount: return self.json_out(404,{"error":"Arkadaş isteği bulunamadı."})
            return self.json_out(200,{"message":"Arkadaş isteği kabul edildi."})
        if route=="/api/messages": return self.send_message(user,data)
        return self.json_out(404,{"error":"İşlem bulunamadı."})
    def register(self,data):
        name=str(data.get("name","")).strip()[:80]; email=str(data.get("email","")).strip().lower()[:254]; password=str(data.get("password",""))
        if not name: return self.json_out(400,{"error":"Adını yaz."})
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email): return self.json_out(400,{"error":"Geçerli bir e-posta yaz."})
        if not 8<=len(password)<=256: return self.json_out(400,{"error":"Şifre 8 ile 256 karakter arasında olmalı."})
        if not mail_ready(): return self.json_out(503,{"error":"E-posta gönderimi ayarlanmamış. Render Environment bölümüne e-posta sağlayıcı ayarlarını ekle."})
        with connect_db() as db:
            if db.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone(): return self.json_out(409,{"error":"Bu e-posta ile hesap zaten var. Giriş yap."})
        salt=secrets.token_bytes(16)
        ok,msg=issue_email_code(email,"register",{"name":name,"password_hash":pw_hash(password,salt),"password_salt":salt.hex()})
        return self.json_out(200 if ok else (429 if "bekle" in msg else 503),{"message":msg} if ok else {"error":msg})
    def verify_registration(self,data):
        email=str(data.get("email","")).strip().lower()[:254]; code=str(data.get("code","")).strip()
        if not re.fullmatch(r"\d{6}",code): return self.json_out(400,{"error":"E-postadaki 6 haneli kodu yaz."})
        with connect_db() as db:
            row,error=check_code(db,email,"register",code)
            if error: return self.json_out(400,{"error":error})
            payload=json.loads(row["payload"])
            try:
                cur=db.execute("INSERT INTO users(name,email,password_hash,password_salt,created_at) VALUES(?,?,?,?,?)",(payload["name"],email,payload["password_hash"],payload["password_salt"],int(time.time())))
                uid=cur.lastrowid
            except sqlite3.IntegrityError:
                db.execute("DELETE FROM email_codes WHERE email=? AND purpose='register'",(email,))
                return self.json_out(409,{"error":"Bu e-posta ile hesap zaten var. Giriş yap."})
            db.execute("DELETE FROM email_codes WHERE email=? AND purpose='register'",(email,))
        return self.json_out(201,{"user":{"id":uid,"name":payload["name"],"email":email}},self.issue_session(uid))
    def login(self,data):
        email=str(data.get("email","")).strip().lower()[:254]; password=str(data.get("password",""))
        with connect_db() as db: row=db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if not row or not hmac.compare_digest(pw_hash(password,bytes.fromhex(row["password_salt"])),row["password_hash"]): return self.json_out(401,{"error":"E-posta veya şifre hatalı."})
        return self.json_out(200,{"user":{"id":row["id"],"name":row["name"],"email":row["email"]}},self.issue_session(row["id"]))
    def forgot_password(self,data):
        email=str(data.get("email","")).strip().lower()[:254]
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email): return self.json_out(400,{"error":"Geçerli bir e-posta yaz."})
        if not mail_ready(): return self.json_out(503,{"error":"E-posta gönderimi ayarlanmamış. Render Environment bölümüne e-posta sağlayıcı ayarlarını ekle."})
        with connect_db() as db: exists=db.execute("SELECT 1 FROM users WHERE email=?",(email,)).fetchone()
        if exists:
            ok,msg=issue_email_code(email,"reset",{})
            if not ok and "bekle" not in msg: return self.json_out(503,{"error":msg})
        return self.json_out(200,{"message":"Bu e-posta kayıtlıysa yenileme kodu gönderildi. Gelen kutunu kontrol et."})
    def reset_password(self,data):
        email=str(data.get("email","")).strip().lower()[:254]; code=str(data.get("code","")).strip(); password=str(data.get("password",""))
        if not re.fullmatch(r"\d{6}",code): return self.json_out(400,{"error":"E-postadaki 6 haneli kodu yaz."})
        if not 8<=len(password)<=256: return self.json_out(400,{"error":"Yeni şifre 8 ile 256 karakter arasında olmalı."})
        salt=secrets.token_bytes(16)
        with connect_db() as db:
            row,error=check_code(db,email,"reset",code)
            if error: return self.json_out(400,{"error":error})
            cur=db.execute("UPDATE users SET password_hash=?,password_salt=? WHERE email=?",(pw_hash(password,salt),salt.hex(),email))
            if not cur.rowcount: return self.json_out(400,{"error":"Bu e-postayla kayıtlı hesap bulunamadı."})
            db.execute("DELETE FROM email_codes WHERE email=? AND purpose='reset'",(email,))
            db.execute("DELETE FROM sessions WHERE user_id=(SELECT id FROM users WHERE email=?)",(email,))
        return self.json_out(200,{"message":"Şifren değiştirildi. Yeni şifrenle giriş yapabilirsin."})
    def logout(self,data):
        token=""
        for part in self.headers.get("Cookie","").split(";"):
            key,_,value=part.strip().partition("=")
            if key=="pk_session": token=value
        if token:
            with connect_db() as db: db.execute("DELETE FROM sessions WHERE token_hash=?",(token_hash(token),))
        return self.json_out(200,{"message":"Çıkış yapıldı."},{"Set-Cookie":"pk_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
    def send_friend_request(self,user,data):
        email=str(data.get("email","")).strip().lower()[:254]
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email): return self.json_out(400,{"error":"Geçerli bir e-posta yaz."})
        with connect_db() as db:
            friend=db.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
            if not friend: return self.json_out(404,{"error":"Bu e-postayla hesap bulunamadı. Arkadaşının önce kayıt olması gerekiyor."})
            fid=friend["id"]
            if fid==user["id"]: return self.json_out(400,{"error":"Kendine arkadaşlık isteği gönderemezsin."})
            old=db.execute("SELECT id,status,sender_id,receiver_id FROM friend_requests WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)",(user["id"],fid,fid,user["id"])).fetchone()
            if old:
                if old["status"]=="accepted": return self.json_out(409,{"error":"Bu kişi zaten arkadaş listende."})
                if old["sender_id"]==fid:
                    db.execute("UPDATE friend_requests SET status='accepted' WHERE id=?",(old["id"],))
                    return self.json_out(200,{"message":"İkiniz de istek göndermişsiniz; artık arkadaşsınız."})
                return self.json_out(409,{"error":"Bu kişiye zaten istek gönderdin."})
            db.execute("INSERT INTO friend_requests(sender_id,receiver_id,status,created_at) VALUES(?,?,'pending',?)",(user["id"],fid,int(time.time())))
        return self.json_out(201,{"message":"Arkadaşlık isteği gönderildi. Kabul edilince mesajlaşabilirsiniz."})
    def send_message(self,user,data):
        try: fid=int(data.get("friend_id",0))
        except (ValueError,TypeError): return self.json_out(400,{"error":"Arkadaş seçilmedi."})
        body=str(data.get("body","")).strip()
        if not body: return self.json_out(400,{"error":"Mesaj boş olamaz."})
        if len(body)>2000: return self.json_out(400,{"error":"Mesaj en fazla 2000 karakter olabilir."})
        with connect_db() as db:
            ok=db.execute("SELECT 1 FROM friend_requests WHERE status='accepted' AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?))",(user["id"],fid,fid,user["id"])).fetchone()
            if not ok: return self.json_out(403,{"error":"Önce arkadaşlık isteği kabul edilmeli."})
            cur=db.execute("INSERT INTO messages(sender_id,receiver_id,body,created_at) VALUES(?,?,?,?)",(user["id"],fid,body,int(time.time())))
            mid=cur.lastrowid
        return self.json_out(201,{"message":{"id":mid,"sender_id":user["id"],"receiver_id":fid,"body":body,"created_at":int(time.time())}})
    def log_message(self,fmt,*args): print("[PostaKapi] "+fmt%args)

if __name__=="__main__":
    initialize_db()
    print(f"PostaKapı sunucusu çalışıyor: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
