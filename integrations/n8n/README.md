# ربط FlowCRM مع n8n

الفكرة: أي قناة (فورم، واتساب، انستجرام...) تبعت بيانات العميل إلى **n8n**، و n8n
يسجّل الدخول على FlowCRM وينده `POST /v1/contacts/upsert` — اللي بيعمل العميل +
محادثة + أول رسالة + تقييم AI تلقائي. وبما إن الـ upsert **idempotent**، تكرار نفس
العميل (نفس `external_id`) مش بيعمل تكرار.

```
[القناة] ──> [n8n Webhook] ──> [Login: /v1/auth/login] ──> [Upsert: /v1/contacts/upsert] ──> FlowCRM
```

## المتطلبات
- FlowCRM شغّال على `http://127.0.0.1:8000` (شغّله بـ `uvicorn app.main:app --reload`).
- Node.js متسطّب (عندك v24 ✅).
- مستخدم admin موجود في FlowCRM. الـ workflow متظبّط افتراضيًا على
  `ana@acme.io` / `password123` (سجّلناه قبل كده). غيّره من node **FlowCRM Login**
  لو بتستخدم حساب تاني.

## الخطوات

### 1) شغّل n8n محليًا
```powershell
npx n8n
```
أول مرة هينزّل n8n (ممكن ياخد كام دقيقة). بعد ما يشتغل، افتح:
**http://localhost:5678** واعمل حساب owner (إيميل/باسورد محلي لـ n8n نفسه).

### 2) استورد الـ workflow
- من n8n: القائمة (فوق على الشمال) → **Import from File**
- اختار الملف: `integrations/n8n/flowcrm-lead-ingestion.json`
- (اختياري) افتح node **FlowCRM Login** وغيّر الإيميل/الباسورد لو لازم.

### 3) جرّبه
- دوس **Test workflow** (أو افتح node Webhook ودوس **Listen for test event**).
- من ترمنال تاني ابعت عميل تجريبي:
```powershell
$body = @{
  external_id = "form-1001"
  full_name   = "Mahmoud Test"
  email       = "mahmoud@test.com"
  phone       = "+201234567890"
  channel     = "web_form"
  message     = "عايز اعرف الاسعار، جاهز اشترك"
} | ConvertTo-Json
Invoke-RestMethod "http://localhost:5678/webhook-test/flowcrm-lead" -Method Post -Body $body -ContentType "application/json"
```
المفروض ترجع بيانات العميل اللي اتعمل في FlowCRM (مع `lead_score` و `is_hot_lead`).

### 4) فعّله للإنتاج
دوس **Active** (فوق على اليمين). دلوقتي الرابط الدائم للـ webhook يبقى:
```
http://localhost:5678/webhook/flowcrm-lead
```
(لاحظ: `webhook` مش `webhook-test` لما يكون Active).

## الحقول المتوقعة في الـ payload
| الحقل | إجباري؟ | ملاحظات |
|---|---|---|
| `external_id` | ✅ | المفتاح الفريد للعميل (عشان الـ idempotency) |
| `full_name` | ✅ | اسم العميل |
| `email` | اختياري | لو موجود لازم يكون إيميل صحيح |
| `phone` | اختياري | |
| `channel` | اختياري | واحد من: messenger, instagram, whatsapp, web_form, landing_page, fb_lead_form, google_form, calendly, email, manual (الافتراضي web_form) |
| `message` | اختياري | أول رسالة من العميل — بتتحلّل بالـ AI |

## ربط القناة الحقيقية (الخطوة الجاية)
الأنبوب ده شغّال مع **أي** مصدر. عشان تربط قناة حقيقية، بتسيب node الـ Login و
الـ Upsert زي ما هما، وتبدّل node **Webhook** بـ trigger القناة:
- **WhatsApp / Messenger / Instagram:** node "WhatsApp Trigger" أو "Facebook" + تظبيط
  الـ Meta App (محتاج حساب Meta Business). بعدها تعمل mapping للحقول.
- **Google Form:** node "Google Forms Trigger".
- **Webhook عام:** سيبه زي ما هو وخلّي المنصة تبعت عليه.

> ملاحظة: n8n محلي بيوصل لـ FlowCRM لأنهم على نفس الجهاز. لو هتنقل n8n للسحابة،
> لازم نرفع FlowCRM أونلاين الأول ونغيّر الـ URL في الـ workflow.
