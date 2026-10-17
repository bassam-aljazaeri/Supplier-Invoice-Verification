export type Role = 'administrator' | 'accountant' | 'approver'
export type Workspace = { id: string; slug: string; name: string; created_at: string }
export type Membership = {
  id: string; workspace_id: string; application_user_id: string; role: Role
  created_at: string; updated_at: string
}
export type OwnMembership = Membership & { workspace: Workspace }
export type Me = {
  user: { id: string; issuer: string; subject: string; created_at: string; updated_at: string }
  memberships: OwnMembership[]
}
export type WorkspaceCreated = { workspace: Workspace; membership: Membership }
export const canCreate = (role?: Role) => role === 'administrator' || role === 'accountant'
export const canManage = (role?: Role) => role === 'administrator'
