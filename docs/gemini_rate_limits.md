# Gemini API Rate Limits

## Current Usage Status (2025-12-07 13:00)

![Gemini API Usage](file:///Users/nemu/.gemini/antigravity/brain/fca91a7e-901f-4f75-b1c3-fe5cc53e6cf1/uploaded_image_1765080034447.png)

### gemini-2.5-flash-lite
- **RPM (Requests Per Minute):** 6/10 ⚠️
- **TPM (Tokens Per Minute):** 1.09K/250K ✅
- **RPD (Requests Per Day):** 34/20 ❌ **EXHAUSTED**
- **Status:** Daily quota exceeded

### gemini-2.5-flash
- **RPM:** 0/5 ✅
- **TPM:** 0/250K ✅
- **RPD:** 0/20 ✅
- **Status:** Available (switched to after flash-lite exhaustion)

## Model Switching Strategy

Our implementation automatically switches models when rate limits are hit:

1. **Primary Model:** `gemini-2.5-flash-lite`
   - Used first for cost efficiency
   - 20 requests/day limit (free tier)
   
2. **Fallback Model:** `gemini-2.5-flash`
   - Automatically activated when flash-lite quota is exhausted
   - 20 requests/day limit (free tier)
   - Higher quality model

## Rate Limit Configuration

### gemini-2.5-flash-lite (Primary)
- **15 RPM** (Requests Per Minute) = 4 seconds per request minimum
- **250K TPM** (Tokens Per Minute) = handled by API
- **20 RPD** (Requests Per Day) = daily limit (free tier)

### gemini-2.5-flash (Fallback)
- **15 RPM** (Requests Per Minute) = 4 seconds per request minimum  
- **250K TPM** (Tokens Per Minute) = handled by API
- **20 RPD** (Requests Per Day) = daily limit (free tier)

## Implementation Details

The `GeminiExtractor` class enforces these limits:

```python
self.request_interval = 4.0  # 15 RPM = 60s / 15 = 4s per request
self.daily_limit = 1000      # Conservative limit
```

### Automatic Fallback Logic

When a `429 RESOURCE_EXHAUSTED` error is detected:
1. Check current model
2. If using `gemini-2.5-flash-lite`, switch to `gemini-2.5-flash`
3. Retry request immediately with new model
4. Continue processing without interruption

## Daily Processing Capacity

With automatic model switching:
- **flash-lite quota:** 20 requests/day
- **flash quota:** 20 requests/day
- **Total capacity:** ~40 requests/day (with fallback)

## Best Practices

1. **Use Sequential Processing:** Process beers one-by-one to maximize brewery hint benefits
2. **Skip Already Enriched:** Only process beers without Gemini data
3. **Monitor Usage:** Check API console regularly
4. **Batch Processing:** Process in small batches (10-50 beers) to manage quotas
5. **Daily Resets:** Quotas reset at midnight UTC

## Upgrade Options

For higher throughput, consider upgrading to paid tier:
- **Pay-as-you-go:** Higher RPM and RPD limits
- **Enterprise:** Custom quotas and SLA

## Current Status

✅ **Automatic model switching implemented**  
✅ **Sequential enrichment working**  
⚠️ **flash-lite quota exhausted (34/20 used)**  
✅ **flash quota available (0/20 used)**  

**Recommendation:** Continue using `sequential_enrich.py` which will automatically use `gemini-2.5-flash` for remaining beers.
