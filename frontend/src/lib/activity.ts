import type { Meta } from '../api/types'
import { STATUS_LABEL } from './format'

const text = (value: unknown): string => (typeof value === 'string' ? value : '')
const status = (value: unknown): string => STATUS_LABEL[value as keyof typeof STATUS_LABEL] ?? text(value)

/**
 * One sentence per event. The activity feeds and the live toasts both use it,
 * so a change reads the same wherever it shows up.
 */
export function describe(type: string, actor: string, meta: Meta, meId?: string): string {
  const task = `“${text(meta.task_title)}”`
  switch (type) {
    case 'task_created':
      return `${actor} created ${task}`
    case 'task_moved':
      return `${actor} moved ${task} from ${status(meta.from_status)} to ${status(meta.to_status)}`
    case 'task_assigned': {
      if (!meta.assignee_id) {
        return meta.reason === 'member_removed'
          ? `${task} was unassigned when ${text(meta.previous_assignee_name)} was removed`
          : `${actor} unassigned ${task}`
      }
      const self = actor === 'You'
      const to = meta.assignee_id === meId ? (self ? 'yourself' : 'you') : text(meta.assignee_name)
      return `${actor} assigned ${task} to ${to}`
    }
    case 'task_updated':
      return `${actor} edited ${task}`
    case 'task_deleted':
      return `${actor} deleted ${task}`
    case 'comment_added':
      return `${actor} commented on ${task}`
    case 'member_invited':
      return meta.member_id === meId
        ? `${actor} added you to the project`
        : `${actor} invited ${text(meta.member_name)}`
    case 'member_removed':
      return `${actor} removed ${text(meta.member_name)}`
    case 'project_deleted':
      return `${actor} deleted the project`
    default:
      return `${actor} made a change`
  }
}
