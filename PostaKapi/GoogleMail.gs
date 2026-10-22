// Run setupPostaKapi() once, then copy its execution log token into Render.
function setupPostaKapi() {
  const secret = Utilities.getUuid() + Utilities.getUuid();
  PropertiesService.getScriptProperties().setProperty("POSTAKAPI_SECRET", secret);
  console.log("MAIL_APPS_SCRIPT_TOKEN=" + secret);
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents || "{}");
    const secret = PropertiesService.getScriptProperties().getProperty("POSTAKAPI_SECRET");
    if (!secret || data.token !== secret) {
      return jsonResponse({ ok: false });
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.to || "")) {
      return jsonResponse({ ok: false });
    }
    if (!/^PostaKapı (hesap oluşturma|şifre yenileme) kodun$/.test(data.subject || "") ||
        !/PostaKapı (hesap oluşturma|şifre yenileme) kodun: \d{6}/.test(data.text || "")) {
      return jsonResponse({ ok: false });
    }
    MailApp.sendEmail({
      to: data.to,
      subject: data.subject,
      body: data.text,
      name: "PostaKapı"
    });
    return jsonResponse({ ok: true });
  } catch (err) {
    return jsonResponse({ ok: false });
  }
}

function jsonResponse(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
