# Cloudflare Free Tunnel Runbook – RC2‑07  
**Eli Decision A7**  

---

## 1. Ownership & Access Control (Eli A7)

| Item | Detail |
|------|--------|
| **Account Owner** | ElsebaeyPharma (company) |
| **Technical Operator** | Eli – *Super Admin* / tunnel operator |
| **2‑Factor Authentication** | Mandatory for **all** Cloudflare logins. CEO/Owner holds **printed offline** recovery codes in a secure safe. |
| **Secret Management** | No tunnel tokens, API keys, or `.env` files are ever committed to Git, stored in this repository, or shared with AI agents. All secrets live only on the production host with `chmod 600`. |

---

## 2. Cloudflare Free‑Plan Tunnel Deployment

### 2.1 Network Bindings (Security‑First)

- **API** → `127.0.0.1:8000` (host‑only)  
- **PostgreSQL** → `127.0.0.1:5432` (host‑only)  

> **Never** expose these ports to the public internet.

### 2.2 Trusted Proxy Configuration

```bash
export RATE_LIMIT_TRUSTED_PROXIES=127.0.0.1   # or the Docker tunnel subnet (e.g., 172.18.0.0/16)
```

Only requests coming from the trusted tunnel peer will have their `CF-Connecting-IP` header honored.

### 2.3 Deployment Command

```bash
# Ensure .env is present on the host, chmod 600, and NOT in Git
docker compose -f docker-compose.prod.yml --profile tunnel up -d
```

### 2.4 Post‑Deploy Validation

| Endpoint | Expected Response |
|----------|-------------------|
| `https://<custom‑domain>/livez` | `200 OK` |
| `https://<custom‑domain>/readyz` | `200 OK` |
| TLS Edge Certificate | Valid, issued by Cloudflare |
| Header `X-Request-ID` | Present and unique per request |

If any check fails, abort and run the **Kill‑Switch** (see §4).

---

## 3. Zero‑Blocker UAT Fallback (Eli A7)

If the custom domain or Cloudflare account is not provisioned by the UAT deadline:

1. Run the stack **without** the tunnel profile, exposing the API only on the LAN:

   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

2. Access the application via `http://127.0.0.1:8000` from any machine on the same LAN.  
3. No additional delay is introduced; UAT proceeds immediately.

---

## 4. Backup, Rollback & Incident Kill‑Switch

### 4.1 Immediate Public Disconnect (Kill‑Switch)

```bash
docker compose -f docker-compose.prod.yml stop cloudflared
```

- Terminates the public tunnel instantly.  
- The API and PostgreSQL remain running locally for diagnostics or graceful shutdown.

### 4.2 Daily Database Backup

```bash
pg_dump -Fc -U <db_user> -d <db_name> -f /backups/$(date +%F)_elsebaey.dump
```

- Verify backup integrity each day (`pg_restore --list`).

### 4.3 Quarterly Restore Drill (R7)

1. Pick the latest daily dump.  
2. Restore to a staging database:

   ```bash
   pg_restore -c -U <db_user> -d <staging_db> /backups/<date>_elsebaey.dump
   ```

3. Run the **33‑table parity script** (provided in `scripts/verify_parity.sql`).  
4. Document results; any discrepancy triggers a full incident review.

---

## 5. Short Arabic Operations Summary (`ملخص التشغيل السريع`)

- **الملكية**: حساب Cloudflare والنطاق المخصص مملوكان لشركة ElsebaeyPharma.  
- **المسؤول الفني**: إيلي هو المشرف الأعلى ومشغل النفق.  
- **المصادقة الثنائية**: إلزامية لجميع عمليات الدخول إلى Cloudflare؛ يحتفظ الرئيس التنفيذي/المالك بأكواد الاستعادة المطبوعة غير المتصلة بالإنترنت.  
- **عدم تخزين الأسرار**: لا تُحفظ رموز النفق أو مفاتيح API أو ملفات `.env` في المستودع أو تُشارك مع أي وكيل ذكاء اصطناعي.  
- **نشر النفق**: API على `127.0.0.1:8000`، PostgreSQL على `127.0.0.1:5432`، تشغيل `docker compose … --profile tunnel up -d`.  
- **التحقق**: `/livez` و `/readyz` يجب أن تُعيد `200`، شهادة TLS صالحة، وجود رأس `X-Request-ID`.  
- **البديل للـ UAT**: إذا لم يُجهّز النطاق، يُشغَّل التطبيق محليًا على LAN عبر `docker compose … up -d` دون ملف تعريف النفق.  
- **إيقاف الطوارئ**: `docker compose … stop cloudflared` يقطع الاتصال العام فورًا.  
- **النسخ الاحتياطي**: `pg_dump -Fc` يوميًا، واختبار استعادة ربع سنوي مع فحص تماثل 33 جدولًا.  

---  

*Prepared by Eli – RC2‑07 – 2026‑11‑21*
