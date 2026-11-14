// Galla settings for login and cloud sync.
// Leave these empty to keep Galla browser-only.
// To turn on sync, paste your Supabase project's URL and anon (publishable) key from
// Supabase dashboard -> Project Settings -> API. The anon key is meant to be public;
// row-level security in supabase/schema.sql keeps each person's data private.
// Never put the service_role key here.
window.GALLA_CONFIG = {
  supabaseUrl: "",
  supabaseAnonKey: ""
};
