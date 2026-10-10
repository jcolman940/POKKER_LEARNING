import { ChoiceGroup, type ChoiceProps } from './ChoiceGroup'

export function SegmentList<T extends string>(props: ChoiceProps<T>) {
  return <ChoiceGroup {...props} vertical />
}
