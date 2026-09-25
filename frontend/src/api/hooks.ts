import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  ActivityPage,
  Board,
  Comment,
  Dashboard,
  Page,
  Priority,
  ProjectDetail,
  ProjectSummary,
  Status,
  Task,
} from './types'

export interface TaskFilters {
  assignee?: string
  priority?: Priority
  q?: string
  status?: Status
}
export type SortKey = 'priority' | 'due_date' | 'created_at'
export interface ListParams extends TaskFilters {
  sort: SortKey
  order: 'asc' | 'desc'
  page: number
  page_size: number
}

// ---------------------------------------------------------------- reads

export function useProjects() {
  return useQuery({ queryKey: ['projects'], queryFn: () => api<ProjectSummary[]>('/projects') })
}

export function useProject(id: string) {
  return useQuery({ queryKey: ['project', id], queryFn: () => api<ProjectDetail>(`/projects/${id}`) })
}

export function useBoard(id: string, filters: TaskFilters) {
  return useQuery({
    queryKey: ['project', id, 'board', filters],
    queryFn: () =>
      api<Board>(`/projects/${id}/board`, {
        query: { assignee: filters.assignee, priority: filters.priority, q: filters.q },
      }),
    placeholderData: keepPreviousData,
  })
}

export function useTasks(id: string, params: ListParams) {
  return useQuery({
    queryKey: ['project', id, 'tasks', params],
    queryFn: () => api<Page<Task>>(`/projects/${id}/tasks`, { query: { ...params } }),
    placeholderData: keepPreviousData,
  })
}

export function useTask(projectId: string, taskId: string) {
  return useQuery({
    queryKey: ['project', projectId, 'task', taskId],
    queryFn: () => api<Task>(`/projects/${projectId}/tasks/${taskId}`),
  })
}

export function useComments(projectId: string, taskId: string) {
  return useQuery({
    queryKey: ['project', projectId, 'task', taskId, 'comments'],
    queryFn: () => api<Comment[]>(`/projects/${projectId}/tasks/${taskId}/comments`),
  })
}

export function useActivity(projectId: string) {
  return useInfiniteQuery({
    queryKey: ['project', projectId, 'activity'],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) =>
      api<ActivityPage>(`/projects/${projectId}/activity`, { query: { before: pageParam, limit: 20 } }),
    getNextPageParam: (last) => last.next_before ?? undefined,
  })
}

export function useMyTasks(params: { status?: Status; page: number; page_size: number }) {
  return useQuery({
    queryKey: ['me', 'tasks', params],
    queryFn: () => api<Page<Task>>('/me/tasks', { query: { ...params } }),
    placeholderData: keepPreviousData,
  })
}

export function useDashboard() {
  return useQuery({ queryKey: ['me', 'dashboard'], queryFn: () => api<Dashboard>('/me/dashboard') })
}

// ---------------------------------------------------------------- writes

/** After any change, everything that could show it is marked stale and the visible parts refetch. */
function useRefreshAfterChange() {
  const client = useQueryClient()
  return (projectId?: string) =>
    Promise.all([
      projectId ? client.invalidateQueries({ queryKey: ['project', projectId] }) : undefined,
      client.invalidateQueries({ queryKey: ['projects'] }),
      client.invalidateQueries({ queryKey: ['me'] }),
    ])
}

export function useCreateProject() {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (body: { name: string; description: string }) =>
      api<ProjectSummary>('/projects', { method: 'POST', body }),
    onSuccess: () => refresh(),
  })
}

export function useDeleteProject(projectId: string) {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: () => api<void>(`/projects/${projectId}`, { method: 'DELETE' }),
    onSuccess: () => refresh(),
  })
}

export function useInvite(projectId: string) {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (email: string) => api<unknown>(`/projects/${projectId}/members`, { method: 'POST', body: { email } }),
    onSuccess: () => refresh(projectId),
  })
}

export function useRemoveMember(projectId: string) {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (userId: string) => api<void>(`/projects/${projectId}/members/${userId}`, { method: 'DELETE' }),
    onSuccess: () => refresh(projectId),
  })
}

export interface NewTask {
  title: string
  description: string
  priority: Priority
  due_date: string | null
  assignee_id: string | null
}
export type TaskPatch = Partial<Omit<NewTask, 'due_date' | 'assignee_id'>> & {
  status?: Status
  due_date?: string | null
  assignee_id?: string | null
}

export function useCreateTask(projectId: string) {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (body: NewTask) => api<Task>(`/projects/${projectId}/tasks`, { method: 'POST', body }),
    onSuccess: () => refresh(projectId),
  })
}

export function useUpdateTask(projectId: string) {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: ({ taskId, patch }: { taskId: string; patch: TaskPatch }) =>
      api<Task>(`/projects/${projectId}/tasks/${taskId}`, { method: 'PATCH', body: patch }),
    onSuccess: () => refresh(projectId),
  })
}

export function useDeleteTask(projectId: string) {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (taskId: string) => api<void>(`/projects/${projectId}/tasks/${taskId}`, { method: 'DELETE' }),
    onSuccess: () => refresh(projectId),
  })
}

export function useAddComment(projectId: string, taskId: string) {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: (body: string) =>
      api<Comment>(`/projects/${projectId}/tasks/${taskId}/comments`, { method: 'POST', body: { body } }),
    onSuccess: () => refresh(projectId),
  })
}
