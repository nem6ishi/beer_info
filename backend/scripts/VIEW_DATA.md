# Supabaseデータ確認ツール

ローカルでSupabaseのデータを確認するためのCLIツールです。

## 使い方

### 統計情報を表示
```bash
SUPABASE_URL=<your_url> SUPABASE_SERVICE_KEY=<your_key> python3 scripts/view_data.py stats
```

### 最近のビールを表示
```bash
# デフォルト10件
SUPABASE_URL=<your_url> SUPABASE_SERVICE_KEY=<your_key> python3 scripts/view_data.py recent

# 20件表示
SUPABASE_URL=<your_url> SUPABASE_SERVICE_KEY=<your_key> python3 scripts/view_data.py recent 20
```

### 特定のストアのビールを表示
```bash
SUPABASE_URL=<your_url> SUPABASE_SERVICE_KEY=<your_key> python3 scripts/view_data.py shop "BEER VOLTA" 10
```

ストア名:
- `BEER VOLTA`
- `ちょうせいや`
- `一期一会～る`

### ビールを検索
```bash
SUPABASE_URL=<your_url> SUPABASE_SERVICE_KEY=<your_key> python3 scripts/view_data.py search "IPA"
```

## 環境変数の設定

`.env`ファイルに以下を設定している場合:
```bash
export $(cat .env | xargs) && python3 scripts/view_data.py stats
```

または、エイリアスを作成:
```bash
alias view-db='SUPABASE_URL=<your_url> SUPABASE_SERVICE_KEY=<your_key> python3 scripts/view_data.py'
```

その後:
```bash
view-db stats
view-db recent 20
view-db shop "BEER VOLTA"
view-db search "IPA"
```
