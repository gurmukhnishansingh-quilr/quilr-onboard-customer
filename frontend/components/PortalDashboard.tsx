"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";
import type { Customer, Instance, InternalUser, SessionInfo } from "../lib/types";
import { startMicrosoftLogin } from "../lib/msAuth";

type InstanceForm = {
  name: string;
  bff_url: string;
  status: string;
  pg_host: string;
  pg_port: string;
  pg_user: string;
  pg_password: string;
  neo4j_host: string;
  neo4j_port: string;
  neo4j_user: string;
  neo4j_password: string;
};

type CustomerForm = {
  first_name: string;
  last_name: string;
  department: string;
  email: string;
  vendor: string;
  instance_id: string;
};

const emptyInstanceForm: InstanceForm = {
  name: "",
  bff_url: "",
  status: "active",
  pg_host: "",
  pg_port: "",
  pg_user: "",
  pg_password: "",
  neo4j_host: "",
  neo4j_port: "",
  neo4j_user: "",
  neo4j_password: ""
};

const emptyCustomerForm: CustomerForm = {
  first_name: "",
  last_name: "",
  department: "Cybersecurity",
  email: "",
  vendor: "",
  instance_id: ""
};

type DashboardView = "instances" | "customers";

const viewTitles: Record<DashboardView, string> = {
  instances: "Instances",
  customers: "Customers"
};

const getCustomerNameParts = (customer: Customer) => {
  if (customer.first_name || customer.last_name) {
    return {
      first: customer.first_name || "",
      last: customer.last_name || ""
    };
  }
  const parts = (customer.name || "").trim().split(/\s+/).filter(Boolean);
  return {
    first: parts[0] || "",
    last: parts.slice(1).join(" ")
  };
};

const parseEnvText = (text: string) => {
  const values: Record<string, string> = {};
  text.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      return;
    }
    const idx = trimmed.indexOf("=");
    if (idx === -1) {
      return;
    }
    let key = trimmed.slice(0, idx).trim();
    if (key.toLowerCase().startsWith("export ")) {
      key = key.slice(7).trim();
    }
    key = key.toUpperCase();
    let value = trimmed.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  });
  return values;
};

export default function PortalDashboard({ view = "customers" }: { view?: DashboardView }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingCustomers, setLoadingCustomers] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [instanceForm, setInstanceForm] = useState<InstanceForm>(emptyInstanceForm);
  const [editingInstance, setEditingInstance] = useState<Instance | null>(null);
  const [showInstanceModal, setShowInstanceModal] = useState(false);
  const [instanceModalMode, setInstanceModalMode] = useState<"add" | "edit">("add");
  const [postgresTestStatus, setPostgresTestStatus] = useState<string | null>(null);
  const [neo4jTestStatus, setNeo4jTestStatus] = useState<string | null>(null);
  const [postgresTestBusy, setPostgresTestBusy] = useState(false);
  const [neo4jTestBusy, setNeo4jTestBusy] = useState(false);
  const [pgPasswordVisible, setPgPasswordVisible] = useState(false);
  const [neo4jPasswordVisible, setNeo4jPasswordVisible] = useState(false);

  const [customerForm, setCustomerForm] = useState<CustomerForm>(emptyCustomerForm);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [internalUsers, setInternalUsers] = useState<InternalUser[]>([]);
  const [internalUsersLoading, setInternalUsersLoading] = useState(false);
  const [internalUsersError, setInternalUsersError] = useState<string | null>(null);
  const [adminUsers, setAdminUsers] = useState<InternalUser[]>([]);
  const [adminUsersLoading, setAdminUsersLoading] = useState(false);
  const [adminUsersError, setAdminUsersError] = useState<string | null>(null);
  const [adminUserCreateOpen, setAdminUserCreateOpen] = useState(false);
  const [adminUserForm, setAdminUserForm] = useState({
    first_name: "",
    last_name: "",
    department: "Cybersecurity",
    email: "",
    vendor: ""
  });
  const [adminUserError, setAdminUserError] = useState<string | null>(null);
  const [adminUserBusy, setAdminUserBusy] = useState(false);
  const [internalUserCreateOpen, setInternalUserCreateOpen] = useState(false);
  const [internalUserForm, setInternalUserForm] = useState({
    username: "",
    password: "",
    confirm: ""
  });
  const [internalUserError, setInternalUserError] = useState<string | null>(null);
  const [internalUserBusy, setInternalUserBusy] = useState(false);
  const [internalUserPasswordVisible, setInternalUserPasswordVisible] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [passwordTargetUser, setPasswordTargetUser] = useState<InternalUser | null>(null);
  const [passwordForm, setPasswordForm] = useState({ password: "", confirm: "" });
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [pushMessage, setPushMessage] = useState<string | null>(null);
  const [customerWizardError, setCustomerWizardError] = useState<string | null>(
    null
  );
  const [showCustomerModal, setShowCustomerModal] = useState(false);
  const [customerModalMode, setCustomerModalMode] = useState<"add" | "edit">("add");
  const [customerSearch, setCustomerSearch] = useState("");

  const instanceOptions = useMemo(() => {
    return instances.map((instance) => ({
      value: instance.id,
      label: instance.name
    }));
  }, [instances]);

  const filteredCustomers = useMemo(() => {
    const query = customerSearch.trim().toLowerCase();
    if (!query) {
      return customers;
    }
    return customers.filter((customer) => {
      const values = [
        customer.tenant_name,
        customer.name,
        customer.first_name,
        customer.last_name,
        customer.department,
        customer.tenant_id,
        customer.subscriber,
        customer.instance_name,
        customer.contact_email
      ]
        .filter(Boolean)
        .map((value) => String(value).toLowerCase());
      return values.some((value) => value.includes(query));
    });
  }, [customerSearch, customers]);

  const loadData = async () => {
    setError(null);
    setLoading(true);
    try {
      const sessionInfo = await apiFetch<SessionInfo>("/api/session");
      setSession(sessionInfo);
      if (!sessionInfo.authenticated) {
        setInstances([]);
        setCustomers([]);
        return;
      }
      const [instanceRows] = await Promise.all([apiFetch<Instance[]>("/api/instances")]);
      setInstances(instanceRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load portal data.");
    } finally {
      setLoading(false);
    }
  };

  const loadCustomers = async (refresh = false) => {
    if (!session?.authenticated) {
      setCustomers([]);
      return;
    }
    setLoadingCustomers(true);
    setError(null);
    try {
      const customerRows = await apiFetch<Customer[]>(
        `/api/customers${refresh ? "?refresh=1" : ""}`
      );
      setCustomers(customerRows);
      setPushMessage(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customers.");
    } finally {
      setLoadingCustomers(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  useEffect(() => {
    if (view !== "customers" || !session?.authenticated) {
      return;
    }
    void loadCustomers();
  }, [view, session?.authenticated]);

  const resetInstanceForm = () => {
    setInstanceForm(emptyInstanceForm);
    setEditingInstance(null);
  };

  const resetCustomerForm = () => {
    setCustomerForm(emptyCustomerForm);
    setEditingCustomer(null);
    setInternalUsers([]);
    setInternalUsersLoading(false);
    setInternalUsersError(null);
    setAdminUsers([]);
    setAdminUsersLoading(false);
    setAdminUsersError(null);
    setAdminUserCreateOpen(false);
    setAdminUserForm({
      first_name: "",
      last_name: "",
      department: "Cybersecurity",
      email: "",
      vendor: ""
    });
    setAdminUserError(null);
    setAdminUserBusy(false);
    setInternalUserCreateOpen(false);
    setInternalUserForm({ username: "", password: "", confirm: "" });
    setInternalUserError(null);
    setInternalUserBusy(false);
    setInternalUserPasswordVisible(false);
    setPushMessage(null);
    setPasswordModalOpen(false);
    setPasswordTargetUser(null);
    setPasswordForm({ password: "", confirm: "" });
    setPasswordBusy(false);
    setPasswordError(null);
    setPasswordVisible(false);
  };

  const loadInternalUsers = async (customer: Customer) => {
    if (!customer.instance_id) {
      setInternalUsers([]);
      setInternalUsersError("Assign an instance to view internal users.");
      return;
    }
    if (!customer.tenant_id) {
      setInternalUsers([]);
      setInternalUsersError("Tenant details are missing. Reload the page to refresh.");
      return;
    }
    setInternalUsers([]);
    setInternalUsersError(null);
    setInternalUsersLoading(true);
    try {
      const params = new URLSearchParams({
        instance_id: customer.instance_id,
        tenant_id: customer.tenant_id
      });
      if (customer.subscriber) {
        params.set("subscriber", customer.subscriber);
      }
      const users = await apiFetch<InternalUser[]>(`/api/internal-users?${params.toString()}`);
      setInternalUsers(users);
    } catch (err) {
      setInternalUsersError(
        err instanceof Error ? err.message : "Failed to load internal users."
      );
    } finally {
      setInternalUsersLoading(false);
    }
  };

  const loadAdminUsers = async (customer: Customer) => {
    if (!customer.instance_id) {
      setAdminUsers([]);
      setAdminUsersError("Assign an instance to view admin users.");
      return;
    }
    if (!customer.tenant_id) {
      setAdminUsers([]);
      setAdminUsersError("Tenant details are missing. Reload the page to refresh.");
      return;
    }
    setAdminUsers([]);
    setAdminUsersError(null);
    setAdminUsersLoading(true);
    try {
      const params = new URLSearchParams({
        instance_id: customer.instance_id,
        tenant_id: customer.tenant_id,
        account_type: "oauth"
      });
      if (customer.subscriber) {
        params.set("subscriber", customer.subscriber);
      }
      const users = await apiFetch<InternalUser[]>(`/api/internal-users?${params.toString()}`);
      setAdminUsers(users);
    } catch (err) {
      setAdminUsersError(
        err instanceof Error ? err.message : "Failed to load admin users."
      );
    } finally {
      setAdminUsersLoading(false);
    }
  };

  const openAdminUserCreate = () => {
    setAdminUserCreateOpen(true);
    setAdminUserForm({
      first_name: customerForm.first_name || "",
      last_name: customerForm.last_name || "",
      department: customerForm.department || "Cybersecurity",
      email: customerForm.email || editingCustomer?.contact_email || "",
      vendor: customerForm.vendor || ""
    });
    setAdminUserError(null);
  };

  const createAdminUser = async () => {
    if (!editingCustomer) {
      setAdminUserError("Select a customer first.");
      return;
    }
    const instanceId = editingCustomer.instance_id || customerForm.instance_id;
    if (!instanceId) {
      setAdminUserError("Instance is required for admin user creation.");
      return;
    }
    if (!adminUserForm.first_name.trim() || !adminUserForm.last_name.trim()) {
      setAdminUserError("First name and last name are required.");
      return;
    }
    const email = adminUserForm.email.trim();
    if (!email) {
      setAdminUserError("Email is required.");
      return;
    }
    setAdminUserBusy(true);
    setAdminUserError(null);
    try {
      await apiFetch("/api/internal-users", {
        method: "POST",
        json: {
          instance_id: instanceId,
          tenant_id: editingCustomer.tenant_id || null,
          subscriber: editingCustomer.subscriber || null,
          match_name: `${adminUserForm.first_name} ${adminUserForm.last_name}`.trim(),
          match_email: email,
          account_type: "oauth",
          first_name: adminUserForm.first_name,
          last_name: adminUserForm.last_name,
          username: email,
          email
        }
      });
      setAdminUserCreateOpen(false);
      await loadAdminUsers(editingCustomer);
    } catch (err) {
      setAdminUserError(
        err instanceof Error ? err.message : "Failed to create admin user."
      );
    } finally {
      setAdminUserBusy(false);
    }
  };

  const openInternalUserCreate = () => {
    const email = customerForm.email || editingCustomer?.contact_email || "";
    setInternalUserCreateOpen(true);
    setInternalUserForm({ username: email, password: "", confirm: "" });
    setInternalUserError(null);
    setInternalUserPasswordVisible(false);
  };

  const createInternalUser = async () => {
    if (!editingCustomer) {
      setInternalUserError("Select a customer first.");
      return;
    }
    const instanceId = editingCustomer.instance_id || customerForm.instance_id;
    if (!instanceId) {
      setInternalUserError("Instance is required for internal user creation.");
      return;
    }
    const password = internalUserForm.password.trim();
    if (!password) {
      setInternalUserError("Internal user password is required.");
      return;
    }
    if (password !== internalUserForm.confirm) {
      setInternalUserError("Internal user passwords do not match.");
      return;
    }
    const email = (customerForm.email || editingCustomer.contact_email || "").trim();
    if (!email) {
      setInternalUserError("Customer email is required.");
      return;
    }
    setInternalUserBusy(true);
    setInternalUserError(null);
    try {
      const matchName =
        `${customerForm.first_name} ${customerForm.last_name}`.trim() ||
        editingCustomer.name ||
        null;
      await apiFetch("/api/internal-users", {
        method: "POST",
        json: {
          instance_id: instanceId,
          match_name: matchName || null,
          match_email: email || null,
          first_name: customerForm.first_name,
          last_name: customerForm.last_name,
          username: internalUserForm.username || email,
          email,
          password
        }
      });
      setInternalUserCreateOpen(false);
      setInternalUserForm({ username: "", password: "", confirm: "" });
      await loadInternalUsers(editingCustomer);
    } catch (err) {
      setInternalUserError(
        err instanceof Error ? err.message : "Failed to create internal user."
      );
    } finally {
      setInternalUserBusy(false);
    }
  };

  const openPasswordModal = (userRow: InternalUser) => {
    setPasswordTargetUser(userRow);
    setPasswordForm({ password: "", confirm: "" });
    setPasswordError(null);
    setPasswordVisible(false);
    setPasswordModalOpen(true);
  };

  const closePasswordModal = () => {
    setPasswordModalOpen(false);
    setPasswordTargetUser(null);
    setPasswordForm({ password: "", confirm: "" });
    setPasswordError(null);
    setPasswordVisible(false);
    setPasswordBusy(false);
  };

  const handlePasswordSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingCustomer || !passwordTargetUser) {
      setPasswordError("Select a user first.");
      return;
    }
    if (!editingCustomer.instance_id || !editingCustomer.tenant_id) {
      setPasswordError("Missing tenant or instance details.");
      return;
    }
    if (!passwordForm.password.trim()) {
      setPasswordError("Password is required.");
      return;
    }
    if (passwordForm.password !== passwordForm.confirm) {
      setPasswordError("Passwords do not match.");
      return;
    }
    setPasswordBusy(true);
    setPasswordError(null);
    try {
      await apiFetch("/api/internal-users/password", {
        method: "POST",
        json: {
          instance_id: editingCustomer.instance_id,
          tenant_id: editingCustomer.tenant_id,
          subscriber: editingCustomer.subscriber || null,
          user_id: passwordTargetUser.id,
          new_password: passwordForm.password
        }
      });
      closePasswordModal();
    } catch (err) {
      setPasswordError(
        err instanceof Error ? err.message : "Unable to update password."
      );
    } finally {
      setPasswordBusy(false);
    }
  };

  const handleInstanceSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: instanceForm.name,
        bff_url: instanceForm.bff_url || null,
        status: instanceForm.status || "active",
        pg_host: instanceForm.pg_host || null,
        pg_port: instanceForm.pg_port || null,
        pg_user: instanceForm.pg_user || null,
        pg_password: instanceForm.pg_password || null,
        neo4j_host: instanceForm.neo4j_host || null,
        neo4j_port: instanceForm.neo4j_port || null,
        neo4j_user: instanceForm.neo4j_user || null,
        neo4j_password: instanceForm.neo4j_password || null
      };
      if (editingInstance) {
        await apiFetch(`/api/instances/${editingInstance.id}`, {
          method: "PUT",
          json: payload
        });
      } else {
        await apiFetch("/api/instances", { method: "POST", json: payload });
      }
      resetInstanceForm();
      setShowInstanceModal(false);
      setInstanceModalMode("add");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save instance.");
    } finally {
      setBusy(false);
    }
  };

  const submitCustomer = async (pushToNeo4j: boolean) => {
    setBusy(true);
    setError(null);
    setPushMessage(null);
    setCustomerWizardError(null);
    try {
      const customerPayload = {
        name: `${customerForm.first_name} ${customerForm.last_name}`.trim(),
        first_name: customerForm.first_name || null,
        last_name: customerForm.last_name || null,
        department: customerForm.department || null,
        vendor: customerForm.vendor || null,
        contact_email: customerForm.email || null,
        instance_id: customerForm.instance_id || null
      };
      if (customerModalMode === "add" && !customerPayload.instance_id) {
        setCustomerWizardError("Select an instance before onboarding.");
        return;
      }
      let instanceId = customerForm.instance_id || "";
      let createdCustomerId: string | null = null;
      if (editingCustomer) {
        await apiFetch(`/api/customers/${editingCustomer.id}`, {
          method: "PUT",
          json: customerPayload
        });
        createdCustomerId = editingCustomer.id;
        instanceId = editingCustomer.instance_id || instanceId;
      } else {
        const response = await apiFetch<Customer>("/api/customers", {
          method: "POST",
          json: customerPayload
        });
        createdCustomerId = response.id;
        instanceId = response.instance_id || instanceId;
      }
      if (pushToNeo4j) {
        if (!createdCustomerId) {
          setError("Customer must be saved before pushing to Neo4j.");
          return;
        }
        await apiFetch(`/api/customers/${createdCustomerId}/neo4j`, {
          method: "POST"
        });
        setPushMessage("Customer pushed to Neo4j.");
      }
      resetCustomerForm();
      setShowCustomerModal(false);
      setCustomerModalMode("add");
      await loadData();
      await loadCustomers(true);
    } catch (err) {
      let message = err instanceof Error ? err.message : "Unable to save customer.";
      if (
        message === "Internal Server Error" ||
        message === "Bad Gateway" ||
        message.startsWith("Request failed with status 5")
      ) {
        try {
          const bffError = await apiFetch<{ detail?: string; at?: string }>(
            "/api/bff-error"
          );
          if (bffError?.detail) {
            message = bffError.detail;
          }
        } catch (fetchErr) {
          // Keep the original message when fallback lookup fails.
        }
      }
      setError(message);
      setCustomerWizardError(message);
    } finally {
      setBusy(false);
    }
  };

  const handleCustomerSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    await submitCustomer(false);
  };

  const handleDeleteInstance = async (instance: Instance) => {
    if (!confirm(`Delete instance ${instance.name}?`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/instances/${instance.id}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete instance.");
    } finally {
      setBusy(false);
    }
  };

  const openAddInstance = () => {
    setInstanceModalMode("add");
    setEditingInstance(null);
    setInstanceForm(emptyInstanceForm);
    setPostgresTestStatus(null);
    setNeo4jTestStatus(null);
    setPgPasswordVisible(false);
    setNeo4jPasswordVisible(false);
    setShowInstanceModal(true);
  };

  const openEditInstance = (instance: Instance) => {
    setInstanceModalMode("edit");
    setEditingInstance(instance);
    setInstanceForm({
      name: instance.name,
      bff_url: instance.bff_url || "",
      status: instance.status || "active",
      pg_host: instance.pg_host || "",
      pg_port: instance.pg_port || "",
      pg_user: instance.pg_user || "",
      pg_password: instance.pg_password || "",
      neo4j_host: instance.neo4j_host || "",
      neo4j_port: instance.neo4j_port || "",
      neo4j_user: instance.neo4j_user || "",
      neo4j_password: instance.neo4j_password || ""
    });
    setPostgresTestStatus(null);
    setNeo4jTestStatus(null);
    setPgPasswordVisible(false);
    setNeo4jPasswordVisible(false);
    setShowInstanceModal(true);
  };

  const closeInstanceModal = () => {
    setShowInstanceModal(false);
    setInstanceModalMode("add");
    resetInstanceForm();
    setPostgresTestStatus(null);
    setNeo4jTestStatus(null);
    setPostgresTestBusy(false);
    setNeo4jTestBusy(false);
    setPgPasswordVisible(false);
    setNeo4jPasswordVisible(false);
  };

  const handleDeleteCustomer = async (customer: Customer) => {
    if (!confirm(`Delete customer ${customer.name}?`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/api/customers/${customer.id}`, { method: "DELETE" });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete customer.");
    } finally {
      setBusy(false);
    }
  };

  const openAddCustomer = () => {
    setCustomerModalMode("add");
    setEditingCustomer(null);
    setCustomerForm(emptyCustomerForm);
    setInternalUserCreateOpen(false);
    setInternalUserForm({ username: "", password: "", confirm: "" });
    setInternalUserError(null);
    setInternalUserPasswordVisible(false);
    setInternalUserBusy(false);
    setAdminUserCreateOpen(false);
    setAdminUserForm({
      first_name: "",
      last_name: "",
      department: "Cybersecurity",
      email: "",
      vendor: ""
    });
    setAdminUserError(null);
    setAdminUserBusy(false);
    setCustomerWizardError(null);
    setPushMessage(null);
    setShowCustomerModal(true);
  };

  const openEditCustomer = (customer: Customer) => {
    setCustomerModalMode("edit");
    setEditingCustomer(customer);
    setCustomerForm({
      first_name: customer.first_name || "",
      last_name: customer.last_name || "",
      department: customer.department || "",
      email: customer.contact_email || "",
      vendor: customer.vendor || "",
      instance_id: customer.instance_id || ""
    });
    setInternalUserCreateOpen(false);
    setInternalUserForm({
      username: customer.contact_email || "",
      password: "",
      confirm: ""
    });
    setInternalUserError(null);
    setInternalUserPasswordVisible(false);
    setInternalUserBusy(false);
    setAdminUserCreateOpen(false);
    setAdminUserForm({
      first_name: customer.first_name || "",
      last_name: customer.last_name || "",
      department: customer.department || "Cybersecurity",
      email: customer.contact_email || "",
      vendor: customer.vendor || ""
    });
    setAdminUserError(null);
    setAdminUserBusy(false);
    setCustomerWizardError(null);
    setPushMessage(null);
    setShowCustomerModal(true);
    void loadInternalUsers(customer);
    void loadAdminUsers(customer);
  };

  const closeCustomerModal = () => {
    setShowCustomerModal(false);
    setCustomerModalMode("add");
    resetCustomerForm();
    setEditingCustomer(null);
    setInternalUserCreateOpen(false);
    setInternalUserError(null);
    setInternalUserBusy(false);
    setAdminUserCreateOpen(false);
    setAdminUserError(null);
    setAdminUserBusy(false);
    setCustomerWizardError(null);
    setPushMessage(null);
  };

  const handleEnvUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const content = await file.text();
    const values = parseEnvText(content);
    const update = (prev: InstanceForm): InstanceForm => ({
      ...prev,
      pg_host: values.PG_HOST ?? prev.pg_host,
      pg_port: values.PG_PORT ?? prev.pg_port,
      pg_user: values.PG_USER ?? prev.pg_user,
      pg_password: values.PG_PASSWORD ?? prev.pg_password,
      neo4j_host: values.NEO4J_HOST ?? prev.neo4j_host,
      neo4j_port: values.NEO4J_PORT ?? prev.neo4j_port,
      neo4j_user: values.NEO4J_USER ?? prev.neo4j_user,
      neo4j_password: values.NEO4J_PASSWORD ?? prev.neo4j_password
    });
    setInstanceForm(update);
    event.target.value = "";
  };

  const runPostgresTest = async () => {
    const form = instanceForm;
    const instanceId = editingInstance?.id;
    setPostgresTestBusy(true);
    setPostgresTestStatus("Testing Postgres...");
    try {
      await apiFetch("/api/test/postgres", {
        method: "POST",
        timeout: 10000,
        json: {
          instance_id: instanceId,
          host: form.pg_host,
          port: form.pg_port ? Number(form.pg_port) : null,
          user: form.pg_user,
          password: form.pg_password
        }
      });
      setPostgresTestStatus("Postgres connection OK.");
    } catch (err) {
      setPostgresTestStatus(err instanceof Error ? err.message : "Postgres test failed.");
    } finally {
      setPostgresTestBusy(false);
    }
  };

  const runNeo4jTest = async () => {
    const form = instanceForm;
    const instanceId = editingInstance?.id;
    setNeo4jTestBusy(true);
    setNeo4jTestStatus("Testing Neo4j...");
    try {
      await apiFetch("/api/test/neo4j", {
        method: "POST",
        timeout: 10000,
        json: {
          instance_id: instanceId,
          host: form.neo4j_host,
          port: form.neo4j_port ? Number(form.neo4j_port) : null,
          user: form.neo4j_user,
          password: form.neo4j_password
        }
      });
      setNeo4jTestStatus("Neo4j connection OK.");
    } catch (err) {
      setNeo4jTestStatus(err instanceof Error ? err.message : "Neo4j test failed.");
    } finally {
      setNeo4jTestBusy(false);
    }
  };

  const handleLogout = async () => {
    await apiFetch("/auth/logout");
    await loadData();
  };

  if (loading && !session) {
    return (
      <main className="cyber-grid">
        <section className="hero-card animate-in">
          <h1 className="neon-text pulse">Loading portal...</h1>
          <p className="status">Warming up your onboarding control deck.</p>
        </section>
      </main>
    );
  }

  if (!session?.authenticated) {
    return (
      <main className="cyber-grid">
        <section className="hero">
          <div className="hero-card animate-in hover-lift">
            <span className="badge pulse">Auth Required</span>
            <h1 className="neon-flicker">Sign in to manage customers.</h1>
            <p>
              Use Microsoft OAuth to unlock the onboarding portal and start provisioning
              instances.
            </p>
            <div className="toolbar">
              <button
                className="button hover-lift pulse"
                onClick={() => {
                  void startMicrosoftLogin();
                }}
              >
                Login with Microsoft
              </button>
              <a className="button secondary hover-glow" href="/">
                Back to home
              </a>
            </div>
          </div>
          <div className="hero-visual animate-in delay-2" aria-hidden="true" />
        </section>
      </main>
    );
  }

  return (
    <main className="dashboard-layout cyber-grid scanline-overlay">
      <aside className="sidebar animate-in-left">
        <div>
          <span className="badge product-name float">
            <img className="product-logo" src="/icons/logo_32x32.png" alt="Quilr" />
            <span className="neon-text">Quilr Onboarding</span>
          </span>
        </div>
        <nav className="sidebar-nav">
          <Link
            href="/dashboard/instances"
            className={view === "instances" ? "active" : ""}
            aria-current={view === "instances" ? "page" : undefined}
          >
            <span className="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" role="img">
                <path
                  d="M7 4h10l4 6-4 6H7L3 10 7 4Z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
                <path
                  d="M7 4v12"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </span>
            Instances
          </Link>
          <Link
            href="/dashboard/customers"
            className={view === "customers" ? "active" : ""}
            aria-current={view === "customers" ? "page" : undefined}
          >
            <span className="nav-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" role="img">
                <path
                  d="M8 13a4 4 0 1 1 8 0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M4 20a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M7 9a5 5 0 0 1 10 0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeDasharray="2 3"
                />
              </svg>
            </span>
            Customers
          </Link>
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-userbar">
            <div className="sidebar-username" title={session.user?.name || "operator"}>
              {session.user?.name || "operator"}
            </div>
            <button
              className="icon-button square"
              onClick={() => void handleLogout()}
              aria-label="Log out"
              title="Log out"
            >
              <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                <path
                  d="M10 6h4m-4 12h4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <path
                  d="M8 4h7a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H8"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <path
                  d="M4 12h9M10 8l3 4-3 4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      <div className="content">
        {error ? (
          <section className="panel" role="alert">
            <strong>Error:</strong> {error}
          </section>
        ) : null}


        {view === "instances" ? (
          <>
            <section className="panel-grid full-height">
              <div className="panel table-panel hover-glow animate-in delay-1">
                <div className="panel-header">
                  <div>
                    <h2 className="neon-text">
                      Instances <span className="table-count">({instances.length})</span>
                    </h2>
                  </div>
                  <button
                    className="icon-button hover-lift"
                    type="button"
                    onClick={openAddInstance}
                    aria-label="Add instance"
                    title="Add instance"
                  >
                    <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                      <path
                        d="M12 5v14M5 12h14"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                </div>
                <div className="table-scroll">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>BFF URL</th>
                        <th>Status</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {instances.map((instance) => (
                        <tr key={instance.id}>
                          <td>{instance.name}</td>
                          <td>{instance.bff_url || "—"}</td>
                          <td>{instance.status || "active"}</td>
                          <td className="toolbar">
                            <button
                              className="icon-button"
                              type="button"
                              onClick={() => {
                                openEditInstance(instance);
                              }}
                              aria-label="Edit instance"
                              title="Edit instance"
                            >
                              <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                <path
                                  d="M4 20h4l10-10-4-4L4 16v4Z"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.6"
                                  strokeLinejoin="round"
                                />
                                <path
                                  d="M13 6l4 4"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.6"
                                  strokeLinecap="round"
                                />
                              </svg>
                            </button>
                            <button
                              className="icon-button"
                              type="button"
                              onClick={() => void handleDeleteInstance(instance)}
                              aria-label="Delete instance"
                              title="Delete instance"
                            >
                              <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                <path
                                  d="M4 7h16"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.6"
                                  strokeLinecap="round"
                                />
                                <path
                                  d="M9 7V5h6v2"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.6"
                                  strokeLinecap="round"
                                />
                                <path
                                  d="M6 7l1 12h10l1-12"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.6"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                />
                              </svg>
                            </button>
                          </td>
                        </tr>
                      ))}
                      {!instances.length ? (
                        <tr>
                          <td colSpan={4} className="status">
                            No instances yet. Start by adding one above.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
            {showInstanceModal ? (
              <div className="modal-backdrop" role="dialog" aria-modal="true">
                <div className="modal neon-border">
                  <div className="modal-header">
                    <div>
                      <span className="badge pulse">Instance Wizard</span>
                      <h2 className="neon-text-orange">{instanceModalMode === "edit" ? "Edit instance" : "Add instance"}</h2>
                    </div>
                    <button
                      className="icon-button square"
                      type="button"
                      onClick={closeInstanceModal}
                      aria-label="Close"
                      title="Close"
                    >
                      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                        <path
                          d="M6 6l12 12M18 6l-12 12"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                        />
                      </svg>
                    </button>
                  </div>
                  <form className="form" onSubmit={handleInstanceSubmit}>
                    <div className="form-section">
                      <h3>Basics</h3>
                      <div className="toolbar">
                        <label className="file-input">
                          Import .env
                          <input
                            type="file"
                            accept=".env,text/plain"
                            onChange={(event) => void handleEnvUpload(event)}
                          />
                        </label>
                      </div>
                      <div className="form">
                        <input
                          className="input"
                          placeholder="Instance name"
                          value={instanceForm.name}
                          onChange={(event) =>
                            setInstanceForm((prev) => ({
                              ...prev,
                              name: event.target.value
                            }))
                          }
                          required
                        />
                        <input
                          className="input"
                          placeholder="BFF URL"
                          value={instanceForm.bff_url}
                          onChange={(event) =>
                            setInstanceForm((prev) => ({
                              ...prev,
                              bff_url: event.target.value
                            }))
                          }
                        />
                        <select
                          className="select"
                          value={instanceForm.status}
                          onChange={(event) =>
                            setInstanceForm((prev) => ({
                              ...prev,
                              status: event.target.value
                            }))
                          }
                        >
                          <option value="active">Active</option>
                          <option value="provisioning">Provisioning</option>
                          <option value="paused">Paused</option>
                        </select>
                      </div>
                    </div>
                      <div className="connection-grid">
                        <div className="accent-card">
                          <h4>Postgres connection</h4>
                          <p className="status">Store connection details for tenant data.</p>
                          <div className="row">
                            <input
                              className="input"
                              placeholder="Postgres host"
                            value={instanceForm.pg_host}
                            onChange={(event) =>
                              setInstanceForm((prev) => ({
                                ...prev,
                                pg_host: event.target.value
                              }))
                            }
                          />
                          <input
                            className="input"
                            placeholder="Postgres port"
                            value={instanceForm.pg_port}
                            onChange={(event) =>
                              setInstanceForm((prev) => ({
                                ...prev,
                                pg_port: event.target.value
                              }))
                            }
                          />
                          <input
                            className="input"
                            placeholder="Postgres user"
                            value={instanceForm.pg_user}
                            onChange={(event) =>
                              setInstanceForm((prev) => ({
                                ...prev,
                                pg_user: event.target.value
                              }))
                            }
                          />
                        </div>
                      <div className="input-with-action">
                        <input
                          className="input"
                          placeholder="Postgres password"
                          type={pgPasswordVisible ? "text" : "password"}
                          value={instanceForm.pg_password}
                          onChange={(event) =>
                            setInstanceForm((prev) => ({
                              ...prev,
                              pg_password: event.target.value
                            }))
                          }
                        />
                        <button
                          className="icon-button"
                          type="button"
                          onClick={() => setPgPasswordVisible((prev) => !prev)}
                          aria-label={pgPasswordVisible ? "Hide password" : "Show password"}
                          title={pgPasswordVisible ? "Hide password" : "Show password"}
                        >
                          {pgPasswordVisible ? (
                            <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                              <path
                                d="M3 3l18 18"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <path
                                d="M7.5 7.5C5 9 3.5 12 3.5 12s2.5 5 8.5 5c1.7 0 3.2-.4 4.5-1"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <path
                                d="M10 10a3 3 0 0 0 4 4"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                            </svg>
                          ) : (
                            <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                              <path
                                d="M3.5 12S6 7 12 7s8.5 5 8.5 5-2.5 5-8.5 5-8.5-5-8.5-5Z"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <circle
                                cx="12"
                                cy="12"
                                r="3"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                              />
                            </svg>
                          )}
                        </button>
                      </div>
                      <div className="toolbar">
                        <button
                          className="icon-button"
                          type="button"
                          onClick={() => void runPostgresTest()}
                          disabled={postgresTestBusy}
                          aria-label="Test Postgres"
                          title="Test Postgres"
                        >
                          <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                            <path
                              d="M8 5l10 7-10 7V5Z"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.6"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </button>
                        {postgresTestStatus ? (
                          <span className="status">{postgresTestStatus}</span>
                        ) : null}
                      </div>
                      </div>
                        <div className="accent-card">
                          <h4>Neo4j connection</h4>
                          <p className="status">Graph database settings for this instance.</p>
                          <div className="row">
                            <input
                              className="input"
                              placeholder="Neo4j host"
                            value={instanceForm.neo4j_host}
                            onChange={(event) =>
                              setInstanceForm((prev) => ({
                                ...prev,
                                neo4j_host: event.target.value
                              }))
                            }
                          />
                          <input
                            className="input"
                            placeholder="Neo4j port"
                            value={instanceForm.neo4j_port}
                            onChange={(event) =>
                              setInstanceForm((prev) => ({
                                ...prev,
                                neo4j_port: event.target.value
                              }))
                            }
                          />
                          <input
                            className="input"
                            placeholder="Neo4j user"
                            value={instanceForm.neo4j_user}
                            onChange={(event) =>
                              setInstanceForm((prev) => ({
                                ...prev,
                                neo4j_user: event.target.value
                              }))
                            }
                          />
                        </div>
                      <div className="input-with-action">
                        <input
                          className="input"
                          placeholder="Neo4j password"
                          type={neo4jPasswordVisible ? "text" : "password"}
                          value={instanceForm.neo4j_password}
                          onChange={(event) =>
                            setInstanceForm((prev) => ({
                              ...prev,
                              neo4j_password: event.target.value
                            }))
                          }
                        />
                        <button
                          className="icon-button"
                          type="button"
                          onClick={() => setNeo4jPasswordVisible((prev) => !prev)}
                          aria-label={neo4jPasswordVisible ? "Hide password" : "Show password"}
                          title={neo4jPasswordVisible ? "Hide password" : "Show password"}
                        >
                          {neo4jPasswordVisible ? (
                            <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                              <path
                                d="M3 3l18 18"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <path
                                d="M7.5 7.5C5 9 3.5 12 3.5 12s2.5 5 8.5 5c1.7 0 3.2-.4 4.5-1"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <path
                                d="M10 10a3 3 0 0 0 4 4"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                            </svg>
                          ) : (
                            <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                              <path
                                d="M3.5 12S6 7 12 7s8.5 5 8.5 5-2.5 5-8.5 5-8.5-5-8.5-5Z"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <circle
                                cx="12"
                                cy="12"
                                r="3"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                              />
                            </svg>
                          )}
                        </button>
                      </div>
                      <div className="toolbar">
                        <button
                          className="icon-button"
                          type="button"
                          onClick={() => void runNeo4jTest()}
                          disabled={neo4jTestBusy}
                          aria-label="Test Neo4j"
                          title="Test Neo4j"
                        >
                          <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                            <path
                              d="M8 5l10 7-10 7V5Z"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.6"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </button>
                        {neo4jTestStatus ? (
                          <span className="status">{neo4jTestStatus}</span>
                        ) : null}
                      </div>
                      </div>
                    </div>
                    <div className="toolbar">
                      <button
                        className="icon-button"
                        type="submit"
                        disabled={busy}
                        aria-label={editingInstance ? "Update instance" : "Add instance"}
                        title={editingInstance ? "Update instance" : "Add instance"}
                      >
                        <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                          <path
                            d="M5 13l4 4L19 7"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                      <button
                        className="icon-button square"
                        type="button"
                        onClick={closeInstanceModal}
                        aria-label="Cancel"
                        title="Cancel"
                      >
                        <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                          <path
                            d="M6 6l12 12M18 6l-12 12"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                          />
                        </svg>
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            ) : null}
          </>
        ) : null}

        {view === "customers" ? (
          <>
            <section className="panel-grid full-height">
              <div className="panel table-panel hover-glow animate-in delay-1">
                <div className="panel-header">
                  <div>
                    <h2 className="neon-text">
                      Customers <span className="table-count">({customers.length})</span>
                    </h2>
                    <p>Track every onboarded customer and their instance.</p>
                  </div>
                  <div className="toolbar">
                    <input
                      className="input search-input"
                      placeholder="Search customers"
                      value={customerSearch}
                      onChange={(event) => setCustomerSearch(event.target.value)}
                      aria-label="Search customers"
                    />
                    <button
                      className="icon-button"
                      type="button"
                      onClick={() => void loadCustomers(true)}
                      disabled={loadingCustomers}
                      aria-label="Reload customers"
                      title="Reload customers"
                    >
                      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                        <path
                          d="M4 12a8 8 0 1 0 2.34-5.66"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                        />
                        <path
                          d="M3 5v5h5"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </button>
                    <button
                      className="icon-button"
                      type="button"
                      onClick={openAddCustomer}
                      aria-label="Add customer"
                      title="Add customer"
                    >
                      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                        <path
                          d="M12 5v14M5 12h14"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
                <div className="table-scroll">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Customer</th>
                        <th>Tenant ID</th>
                        <th>Subscriber</th>
                        <th>Instance</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {loadingCustomers ? (
                        <tr>
                          <td colSpan={5} className="status">
                            Loading tenant data...
                          </td>
                        </tr>
                      ) : null}
                      {filteredCustomers.map((customer) => {
                        const parts = getCustomerNameParts(customer);
                        const customerName =
                          customer.tenant_name ||
                          [parts.first, parts.last].filter(Boolean).join(" ") ||
                          customer.name ||
                          "—";
                        return (
                          <tr key={customer.id}>
                            <td>{customerName}</td>
                            <td>{customer.tenant_id || "—"}</td>
                            <td>{customer.subscriber || "—"}</td>
                            <td>{customer.instance_name || "Unassigned"}</td>
                            <td className="toolbar">
                              <button
                                className="icon-button"
                                type="button"
                                onClick={() => {
                                  openEditCustomer(customer);
                                }}
                                aria-label="Edit customer"
                                title="Edit customer"
                              >
                                <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                  <path
                                    d="M4 20h4l10-10-4-4L4 16v4Z"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="1.6"
                                    strokeLinejoin="round"
                                  />
                                  <path
                                    d="M13 6l4 4"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="1.6"
                                    strokeLinecap="round"
                                  />
                                </svg>
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                      {!filteredCustomers.length && !loadingCustomers ? (
                        <tr>
                          <td colSpan={5} className="status">
                            No customers found.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
            {showCustomerModal ? (
              <div className="modal-backdrop" role="dialog" aria-modal="true">
                <div className="modal neon-border">
                  <div className="modal-header">
                    <div>
                      <span className="badge pulse">Customer Wizard</span>
                      <h2 className="neon-text-orange">{customerModalMode === "edit" ? "Edit customer" : "Add customer"}</h2>
                    </div>
                    <button
                      className="icon-button square"
                      type="button"
                      onClick={closeCustomerModal}
                      aria-label="Close"
                      title="Close"
                    >
                      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                        <path
                          d="M6 6l12 12M18 6l-12 12"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                        />
                      </svg>
                    </button>
                  </div>
                  <form className="form" onSubmit={handleCustomerSubmit}>
                    {customerModalMode === "add" ? (
                      <div className="form-section">
                        <h3>Customer admin details</h3>
                        <div className="form">
                          <input
                            className="input"
                            placeholder="First name"
                            value={customerForm.first_name}
                            onChange={(event) =>
                              setCustomerForm((prev) => ({
                                ...prev,
                                first_name: event.target.value
                              }))
                            }
                            required
                          />
                          <input
                            className="input"
                            placeholder="Last name"
                            value={customerForm.last_name}
                            onChange={(event) =>
                              setCustomerForm((prev) => ({
                                ...prev,
                                last_name: event.target.value
                              }))
                            }
                            required
                          />
                          <input
                            className="input"
                            placeholder="Department"
                            value={customerForm.department}
                            onChange={(event) =>
                              setCustomerForm((prev) => ({
                                ...prev,
                                department: event.target.value
                              }))
                            }
                            required
                          />
                          <input
                            className="input"
                            placeholder="Email"
                            type="email"
                            value={customerForm.email}
                            onChange={(event) =>
                              setCustomerForm((prev) => ({
                                ...prev,
                                email: event.target.value
                              }))
                            }
                            required
                          />
                          <select
                            className="select"
                            value={customerForm.vendor}
                            onChange={(event) =>
                              setCustomerForm((prev) => ({
                                ...prev,
                                vendor: event.target.value
                              }))
                            }
                            required
                          >
                            <option value="">Select vendor</option>
                            <option value="google">Google</option>
                            <option value="microsoft">Microsoft</option>
                          </select>
                        </div>
                      </div>
                    ) : null}
                    {customerModalMode === "edit" ? (
                      <div className="form-section">
                        <div className="panel-header">
                          <h3>Internal users</h3>
                          <div className="toolbar">
                            <button
                              className="icon-button square"
                              type="button"
                              onClick={openInternalUserCreate}
                              aria-label="Create internal user"
                              title="Create internal user"
                            >
                              <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                <path
                                  d="M12 5v14M5 12h14"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.6"
                                  strokeLinecap="round"
                                />
                              </svg>
                            </button>
                          </div>
                        </div>
                        {internalUsersLoading ? (
                          <p className="status">Loading internal users...</p>
                        ) : internalUsersError ? (
                          <p className="status">Error: {internalUsersError}</p>
                        ) : (
                          <div className="form">
                            {internalUserCreateOpen ? (
                              <div className="form">
                                <input
                                  className="input"
                                  placeholder="Username (defaults to email)"
                                  value={internalUserForm.username}
                                  onChange={(event) => {
                                    setInternalUserForm((prev) => ({
                                      ...prev,
                                      username: event.target.value
                                    }));
                                    setInternalUserError(null);
                                  }}
                                />
                                <div className="input-with-action">
                                  <input
                                    className="input"
                                    placeholder="Password"
                                    type={internalUserPasswordVisible ? "text" : "password"}
                                    value={internalUserForm.password}
                                    onChange={(event) => {
                                      setInternalUserForm((prev) => ({
                                        ...prev,
                                        password: event.target.value
                                      }));
                                      setInternalUserError(null);
                                    }}
                                    required
                                    minLength={8}
                                  />
                                  <button
                                    className="icon-button"
                                    type="button"
                                    onClick={() =>
                                      setInternalUserPasswordVisible((prev) => !prev)
                                    }
                                    aria-label="Toggle password visibility"
                                    title={
                                      internalUserPasswordVisible
                                        ? "Hide password"
                                        : "Show password"
                                    }
                                  >
                                    {internalUserPasswordVisible ? (
                                      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                        <path
                                          d="M3 3l18 18"
                                          fill="none"
                                          stroke="currentColor"
                                          strokeWidth="1.6"
                                          strokeLinecap="round"
                                        />
                                        <path
                                          d="M7.5 7.5C5 9 3.5 12 3.5 12s2.5 5 8.5 5c1.7 0 3.2-.4 4.5-1"
                                          fill="none"
                                          stroke="currentColor"
                                          strokeWidth="1.6"
                                          strokeLinecap="round"
                                        />
                                        <path
                                          d="M10 10a3 3 0 0 0 4 4"
                                          fill="none"
                                          stroke="currentColor"
                                          strokeWidth="1.6"
                                          strokeLinecap="round"
                                        />
                                      </svg>
                                    ) : (
                                      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                        <path
                                          d="M3.5 12S6 7 12 7s8.5 5 8.5 5-2.5 5-8.5 5-8.5-5-8.5-5Z"
                                          fill="none"
                                          stroke="currentColor"
                                          strokeWidth="1.6"
                                          strokeLinecap="round"
                                        />
                                        <circle
                                          cx="12"
                                          cy="12"
                                          r="3"
                                          fill="none"
                                          stroke="currentColor"
                                          strokeWidth="1.6"
                                        />
                                      </svg>
                                    )}
                                  </button>
                                </div>
                                <input
                                  className="input"
                                  placeholder="Confirm password"
                                  type={internalUserPasswordVisible ? "text" : "password"}
                                  value={internalUserForm.confirm}
                                  onChange={(event) => {
                                    setInternalUserForm((prev) => ({
                                      ...prev,
                                      confirm: event.target.value
                                    }));
                                    setInternalUserError(null);
                                  }}
                                  required
                                  minLength={8}
                                />
                                <div className="toolbar">
                                  <button
                                    className="icon-button"
                                    type="button"
                                    onClick={() => void createInternalUser()}
                                    disabled={internalUserBusy}
                                    aria-label="Create user"
                                    title="Create user"
                                  >
                                    <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                      <path
                                        d="M5 13l4 4L19 7"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="1.8"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                      />
                                    </svg>
                                  </button>
                                  <button
                                    className="icon-button square"
                                    type="button"
                                    onClick={() => setInternalUserCreateOpen(false)}
                                    aria-label="Cancel"
                                    title="Cancel"
                                  >
                                    <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                      <path
                                        d="M6 6l12 12M18 6l-12 12"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="1.6"
                                        strokeLinecap="round"
                                      />
                                    </svg>
                                  </button>
                                </div>
                                {internalUserError ? (
                                  <p className="status">Error: {internalUserError}</p>
                                ) : null}
                              </div>
                            ) : null}
                            {internalUsers.length ? (
                              <table className="table">
                                <thead>
                                  <tr>
                                    <th>Name</th>
                                    <th>Email</th>
                                    <th>Type</th>
                                    <th />
                                  </tr>
                                </thead>
                                <tbody>
                                  {internalUsers.map((userRow) => (
                                    <tr key={userRow.id || userRow.email || "user"}>
                                      <td>{userRow.name || "—"}</td>
                                      <td>{userRow.email || "—"}</td>
                                      <td>{userRow.account_type || "—"}</td>
                                      <td className="toolbar">
                                        <button
                                          className="icon-button"
                                          type="button"
                                          onClick={() => openPasswordModal(userRow)}
                                          aria-label="Change password"
                                          title="Change password"
                                        >
                                          <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                            <path
                                              d="M7 11a5 5 0 1 1 10 0v3"
                                              fill="none"
                                              stroke="currentColor"
                                              strokeWidth="1.6"
                                              strokeLinecap="round"
                                            />
                                            <rect
                                              x="6"
                                              y="14"
                                              width="12"
                                              height="6"
                                              fill="none"
                                              stroke="currentColor"
                                              strokeWidth="1.6"
                                              strokeLinejoin="round"
                                            />
                                          </svg>
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            ) : (
                              <p className="status">No internal users found.</p>
                            )}
                          </div>
                        )}
                      </div>
                    ) : null}
                    {customerModalMode === "edit" ? (
                      <div className="form-section">
                        <div className="panel-header">
                          <h3>Customer admin users</h3>
                          <div className="toolbar">
                            <button
                              className="icon-button square"
                              type="button"
                              onClick={openAdminUserCreate}
                              aria-label="Add admin user"
                              title="Add admin user"
                            >
                              <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                <path
                                  d="M12 5v14M5 12h14"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.6"
                                  strokeLinecap="round"
                                />
                              </svg>
                            </button>
                          </div>
                        </div>
                        {adminUserCreateOpen ? (
                          <div className="form">
                            <input
                              className="input"
                              placeholder="First name"
                              value={adminUserForm.first_name}
                              onChange={(event) =>
                                setAdminUserForm((prev) => ({
                                  ...prev,
                                  first_name: event.target.value
                                }))
                              }
                              required
                            />
                            <input
                              className="input"
                              placeholder="Last name"
                              value={adminUserForm.last_name}
                              onChange={(event) =>
                                setAdminUserForm((prev) => ({
                                  ...prev,
                                  last_name: event.target.value
                                }))
                              }
                              required
                            />
                            <input
                              className="input"
                              placeholder="Department"
                              value={adminUserForm.department}
                              onChange={(event) =>
                                setAdminUserForm((prev) => ({
                                  ...prev,
                                  department: event.target.value
                                }))
                              }
                            />
                            <input
                              className="input"
                              placeholder="Email"
                              value={adminUserForm.email}
                              onChange={(event) =>
                                setAdminUserForm((prev) => ({
                                  ...prev,
                                  email: event.target.value
                                }))
                              }
                              required
                            />
                            <select
                              className="select"
                              value={adminUserForm.vendor}
                              onChange={(event) =>
                                setAdminUserForm((prev) => ({
                                  ...prev,
                                  vendor: event.target.value
                                }))
                              }
                            >
                              <option value="">Select vendor</option>
                              <option value="google">Google</option>
                              <option value="microsoft">Microsoft</option>
                            </select>
                            <div className="toolbar">
                              <button
                                className="icon-button"
                                type="button"
                                onClick={() => void createAdminUser()}
                                disabled={adminUserBusy}
                                aria-label="Create admin user"
                                title="Create admin user"
                              >
                                <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                  <path
                                    d="M5 13l4 4L19 7"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="1.8"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              </button>
                              <button
                                className="icon-button square"
                                type="button"
                                onClick={() => setAdminUserCreateOpen(false)}
                                aria-label="Cancel"
                                title="Cancel"
                              >
                                <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                                  <path
                                    d="M6 6l12 12M18 6l-12 12"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="1.6"
                                    strokeLinecap="round"
                                  />
                                </svg>
                              </button>
                            </div>
                            {adminUserError ? (
                              <p className="status">Error: {adminUserError}</p>
                            ) : null}
                          </div>
                        ) : null}
                        {adminUsersLoading ? (
                          <p className="status">Loading admin users...</p>
                        ) : adminUsersError ? (
                          <p className="status">Error: {adminUsersError}</p>
                        ) : adminUsers.length ? (
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Type</th>
                              </tr>
                            </thead>
                            <tbody>
                              {adminUsers.map((userRow) => (
                                <tr key={userRow.id || userRow.email || "admin-user"}>
                                  <td>{userRow.name || "—"}</td>
                                  <td>{userRow.email || "—"}</td>
                                  <td>{userRow.account_type || "oauth"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p className="status">No admin users found.</p>
                        )}
                      </div>
                    ) : null}
                    <select
                      className="select"
                      value={customerForm.instance_id}
                      onChange={(event) =>
                        setCustomerForm((prev) => ({
                          ...prev,
                          instance_id: event.target.value
                        }))
                      }
                      disabled={instanceOptions.length === 0}
                      required={customerModalMode === "add"}
                    >
                      <option value="">
                        {instanceOptions.length ? "Select instance" : "No instances yet"}
                      </option>
                      {instanceOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>

                    <div className="toolbar">
                      <button
                        className="icon-button"
                        type="submit"
                        disabled={busy}
                        aria-label={
                          editingCustomer ? "Update customer" : "Onboard customer"
                        }
                        title={editingCustomer ? "Update customer" : "Onboard customer"}
                      >
                        <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                          <path
                            d="M5 13l4 4L19 7"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                      {editingCustomer ? (
                        <button
                          className="icon-button"
                          type="button"
                          disabled={busy}
                          onClick={() => void submitCustomer(true)}
                          aria-label="Push to Neo4j"
                          title="Push to Neo4j"
                        >
                          <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                            <path
                              d="M12 5v10"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.6"
                              strokeLinecap="round"
                            />
                            <path
                              d="M8 9l4-4 4 4"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.6"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                            <path
                              d="M5 19h14"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.6"
                              strokeLinecap="round"
                            />
                          </svg>
                        </button>
                      ) : null}
                      <button
                        className="icon-button square"
                        type="button"
                        onClick={closeCustomerModal}
                        aria-label="Cancel"
                        title="Cancel"
                      >
                        <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                          <path
                            d="M6 6l12 12M18 6l-12 12"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                          />
                        </svg>
                      </button>
                    </div>
                    {customerWizardError ? (
                      <p className="status">Error: {customerWizardError}</p>
                    ) : null}
                    {busy ? (
                      <div className="loader-row" aria-live="polite">
                        <span className="spinner" aria-hidden="true" />
                        <span className="status">Submitting request...</span>
                      </div>
                    ) : null}
                    {pushMessage ? <p className="status">{pushMessage}</p> : null}
                  </form>
                </div>
              </div>
            ) : null}
            {passwordModalOpen && passwordTargetUser ? (
              <div className="modal-backdrop" role="dialog" aria-modal="true">
                <div className="modal neon-border">
                  <div className="modal-header">
                    <div>
                      <span className="badge pulse">Internal User</span>
                      <h2 className="neon-text-orange">Change password</h2>
                    </div>
                    <button
                      className="icon-button square"
                      type="button"
                      onClick={closePasswordModal}
                      aria-label="Close"
                      title="Close"
                    >
                      <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                        <path
                          d="M6 6l12 12M18 6l-12 12"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                        />
                      </svg>
                    </button>
                  </div>
                  <form className="form" onSubmit={handlePasswordSubmit}>
                    <div className="form-section">
                      <p className="status">
                        Updating password for{" "}
                        <strong>{passwordTargetUser.name || passwordTargetUser.email}</strong>
                      </p>
                      <div className="input-with-action">
                        <input
                          className="input"
                          placeholder="New password"
                          type={passwordVisible ? "text" : "password"}
                          value={passwordForm.password}
                          onChange={(event) =>
                            setPasswordForm((prev) => ({
                              ...prev,
                              password: event.target.value
                            }))
                          }
                          required
                          minLength={8}
                        />
                        <button
                          type="button"
                          className="icon-button"
                          onClick={() => setPasswordVisible((prev) => !prev)}
                          aria-label="Toggle password visibility"
                          title={passwordVisible ? "Hide password" : "Show password"}
                        >
                          {passwordVisible ? (
                            <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                              <path
                                d="M3 3l18 18"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <path
                                d="M7.5 7.5C5 9 3.5 12 3.5 12s2.5 5 8.5 5c1.7 0 3.2-.4 4.5-1"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <path
                                d="M10 10a3 3 0 0 0 4 4"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                            </svg>
                          ) : (
                            <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                              <path
                                d="M3.5 12S6 7 12 7s8.5 5 8.5 5-2.5 5-8.5 5-8.5-5-8.5-5Z"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                              />
                              <circle
                                cx="12"
                                cy="12"
                                r="3"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                              />
                            </svg>
                          )}
                        </button>
                      </div>
                      <input
                        className="input"
                        placeholder="Confirm password"
                        type={passwordVisible ? "text" : "password"}
                        value={passwordForm.confirm}
                        onChange={(event) =>
                          setPasswordForm((prev) => ({
                            ...prev,
                            confirm: event.target.value
                          }))
                        }
                        required
                        minLength={8}
                      />
                      {passwordError ? <p className="status">Error: {passwordError}</p> : null}
                    </div>
                    <div className="actions">
                      <button
                        className="icon-button"
                        type="submit"
                        disabled={passwordBusy}
                        aria-label="Update password"
                        title="Update password"
                      >
                        <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                          <path
                            d="M5 13l4 4L19 7"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                      <button
                        className="icon-button square"
                        type="button"
                        onClick={closePasswordModal}
                        aria-label="Cancel"
                        title="Cancel"
                      >
                        <svg viewBox="0 0 24 24" role="img" aria-hidden="true">
                          <path
                            d="M6 6l12 12M18 6l-12 12"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                          />
                        </svg>
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </main>
  );
}
