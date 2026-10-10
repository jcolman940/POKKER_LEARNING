import { ChoiceGroup, type ChoiceProps } from './ChoiceGroup'

export function PillGroup<T extends string>(props: ChoiceProps<T>) {
  return <ChoiceGroup {...props} vertical={false} />
}
