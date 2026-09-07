import { useOutletContext } from 'react-router-dom'
import RecommendationCard from '../../components/RecommendationCard.jsx'

export default function Recommendations() {
  const { data } = useOutletContext()
  return <RecommendationCard recommendations={data.recommendations} />
}
