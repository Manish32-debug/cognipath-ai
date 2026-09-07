import { useOutletContext } from 'react-router-dom'
import CognitiveTwin from '../../components/CognitiveTwin.jsx'

export default function Twin() {
  const { data } = useOutletContext()
  return <CognitiveTwin twin={data.cognitive_twin} />
}
