import { useOutletContext } from 'react-router-dom'
import StudyPlan from '../../components/StudyPlan.jsx'

export default function Plan() {
  const { data } = useOutletContext()
  return <StudyPlan plan={data.study_plan} />
}
