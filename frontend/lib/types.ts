export type Instance = {
  id: string;
  name: string;
  bff_url?: string | null;
  status?: string | null;
  pg_host?: string | null;
  pg_port?: string | null;
  pg_user?: string | null;
  pg_password?: string | null;
  neo4j_host?: string | null;
  neo4j_port?: string | null;
  neo4j_user?: string | null;
  neo4j_password?: string | null;
  created_at: string;
  updated_at: string;
};

export type Customer = {
  id: string;
  name: string;
  first_name?: string | null;
  last_name?: string | null;
  department?: string | null;
  vendor?: string | null;
  contact_email?: string | null;
  comment?: string | null;
  tenant_name?: string | null;
  tenant_id?: string | null;
  subscriber?: string | null;
  instance_id?: string | null;
  instance_name?: string | null;
  created_at: string;
  updated_at: string;
};

export type CustomerComment = {
  id: string;
  customer_id: string;
  tenant_id?: string | null;
  comment: string;
  author_email?: string | null;
  author_name?: string | null;
  created_at: string;
  updated_at: string;
};

export type SessionInfo = {
  authenticated: boolean;
  user?: {
    name?: string;
    email?: string;
    sub?: string;
    mode?: string;
  } | null;
};

export type InternalUser = {
  id?: string | null;
  name?: string | null;
  email?: string | null;
  account_type?: string | null;
};
