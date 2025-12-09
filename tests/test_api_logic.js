
const { createClient } = require('@supabase/supabase-js');
const dotenv = require('dotenv');
const path = require('path');

// Verify .env loading
const envPath = path.resolve(__dirname, '../.env');
console.log('Loading .env from:', envPath);
dotenv.config({ path: envPath });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
    console.error('Missing Supabase credentials');
    console.log('URL:', supabaseUrl);
    console.log('Key:', supabaseKey ? 'Set' : 'Missing');
    process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function testQuery() {
    console.log('Testing query equivalent to: sort=newest');

    const { data, error, count } = await supabase
        .from('beers')
        .select('*', { count: 'exact' })
        .order('first_seen', { ascending: false, nullsLast: true })
        .range(0, 29);

    if (error) {
        console.error('Query Error:', error);
    } else {
        console.log(`Success! Found ${data.length} items. Total count: ${count}`);
        if (data.length > 0) {
            console.log('Sample item:', {
                name: data[0].name,
                first_seen: data[0].first_seen
            });
        }
    }
}

testQuery();
