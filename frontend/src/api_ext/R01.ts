import { req } from '../api'

// Real web learning resources for a concept (spec R01, found with Tavily and cached on the server)
export interface WebResource { title: string; url: string; domain: string; kind: 'docs' | 'article' | 'video'; snippet: string }
export interface WebResources { concept_id: string; status: 'ok' | 'unavailable' | 'disabled'; items: WebResource[]; fetched_at: string | null; label: string }

export const apiR01 = {
  forConcept: (conceptId: string): Promise<WebResources> => req(`/resources/${conceptId}`),
}
