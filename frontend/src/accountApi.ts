import { ApiFailure, privateRequest } from './api.ts'
import type { RequestOptions } from './api.ts'
import type { Me, Membership, Role, Workspace, WorkspaceCreated } from './authTypes.ts'
import type { RecordPage } from './types.ts'
import { isUuid } from './validation.ts'
import { validPage } from './navigation.ts'

const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0
export const isRole = (v: unknown): v is Role => v === 'administrator' || v === 'accountant' || v === 'approver'
export const isWorkspace = (v: unknown): v is Workspace => object(v) && isUuid(v.id) && text(v.slug) && text(v.name) && text(v.created_at)
export const isMembership = (v: unknown): v is Membership => object(v) && isUuid(v.id) && isUuid(v.workspace_id) && isUuid(v.application_user_id) && isRole(v.role) && text(v.created_at) && text(v.updated_at)
export function isMe(v: unknown): v is Me {
  return object(v) && object(v.user) && isUuid(v.user.id) && text(v.user.issuer) && text(v.user.subject) && text(v.user.created_at) && text(v.user.updated_at)
    && Array.isArray(v.memberships) && v.memberships.every((m) => {
      if (!object(m)) return false
      const workspace = m.workspace
      return isMembership(m) && m.application_user_id === (v.user as Record<string, unknown>).id && isWorkspace(workspace) && workspace.id === m.workspace_id
    })
}
const isCreated = (v: unknown): v is WorkspaceCreated => object(v) && isWorkspace(v.workspace) && isMembership(v.membership) && v.membership.workspace_id === v.workspace.id && v.membership.role === 'administrator'
const isMemberPage = (v: unknown): v is RecordPage<Membership> => object(v) && typeof v.limit === 'number' && typeof v.offset === 'number' && validPage({ limit: v.limit, offset: v.offset }) && typeof v.total === 'number' && Number.isSafeInteger(v.total) && v.total >= 0 && Array.isArray(v.items) && v.items.length <= v.limit && v.items.every(isMembership)

export const getMe = (options: RequestOptions = {}) => privateRequest('/me', isMe, options, undefined, 'account')
export function createWorkspace(input: { slug: string; name: string }, options: RequestOptions = {}) {
  const slug = input.slug.trim(), name = input.name.trim()
  if (slug.length > 64 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) || slug === 'local-demo' || !name || name.length > 200) return Promise.reject(new ApiFailure('validation', 'Use a workspace name of 1–200 characters and a slug of 1–64 lowercase letters/digits separated by single hyphens. local-demo is reserved.'))
  return privateRequest('/workspaces', isCreated, options, { slug, name }, 'account')
}
function membershipPath(workspaceId: string, userId?: string) {
  if (!isUuid(workspaceId) || (userId !== undefined && !isUuid(userId))) throw new ApiFailure('validation', 'Use an application-user UUID and an accessible workspace.')
  return `/workspaces/${workspaceId}/memberships${userId ? '/' + userId : ''}`
}
export function getMemberships(workspaceId: string, offset = 0, options: RequestOptions = {}) {
  if (!validPage({ limit: 20, offset })) throw new ApiFailure('validation', 'Invalid page limits.')
  return privateRequest(`${membershipPath(workspaceId)}?limit=20&offset=${offset}`, (v): v is RecordPage<Membership> => isMemberPage(v) && v.items.every((m) => m.workspace_id === workspaceId), options, undefined, 'account')
}
export function addMembership(workspaceId: string, userId: string, role: Role, options: RequestOptions = {}) {
  if (!isUuid(userId) || !isRole(role)) return Promise.reject(new ApiFailure('validation', 'Use an existing application-user UUID and a listed role.'))
  return privateRequest(membershipPath(workspaceId), (v): v is Membership => isMembership(v) && v.workspace_id === workspaceId && v.application_user_id === userId, options, { application_user_id: userId, role }, 'account')
}
export function changeMembership(workspaceId: string, userId: string, role: Role, options: RequestOptions = {}) {
  if (!isRole(role)) return Promise.reject(new ApiFailure('validation', 'Choose a listed role.'))
  return privateRequest(membershipPath(workspaceId, userId), (v): v is Membership => isMembership(v) && v.workspace_id === workspaceId && v.application_user_id === userId, options, { role }, 'account', 'PATCH')
}
export function removeMembership(workspaceId: string, userId: string, options: RequestOptions = {}) {
  return privateRequest(membershipPath(workspaceId, userId), (v): v is undefined => v === undefined, options, undefined, 'account', 'DELETE')
}
