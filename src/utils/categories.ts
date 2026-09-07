export interface CategoryInfo {
  slug: string;
  name: string;
  icon: string;
  description: string;
}

export const CATEGORIES: CategoryInfo[] = [
  {
    slug: 'iluminacao-led',
    name: 'Iluminação LED',
    icon: '💡',
    description: 'Guias sobre LED, luz e lâmpadas para aquário: como escolher, comparar tipos e configurar a iluminação certa para o seu tanque.',
  },
  {
    slug: 'plantas-aquaticas',
    name: 'Plantas Aquáticas',
    icon: '🌿',
    description: 'Fotoperíodo, PAR, watts por litro e tudo sobre iluminação para aquários plantados e aquapaisagismo.',
  },
  {
    slug: 'aquario-marinho',
    name: 'Aquário Marinho',
    icon: '🐠',
    description: 'Iluminação para aquário marinho, reef e corais: LED full spectrum, PAR e as melhores luminárias para água salgada.',
  },
  {
    slug: 'peixes',
    name: 'Peixes',
    icon: '🐟',
    description: 'Fotoperíodo e iluminação ideal para o bem-estar e as cores dos peixes, de tropicais a discus.',
  },
  {
    slug: 'equipamentos',
    name: 'Equipamentos',
    icon: '🔧',
    description: 'Luminárias, calhas, fitas de LED, timers e reviews de equipamentos para aquário por tamanho e orçamento.',
  },
];

export function getCategoryBySlug(slug: string): CategoryInfo | undefined {
  return CATEGORIES.find(c => c.slug === slug);
}

export function getCategoryByName(name: string): CategoryInfo | undefined {
  return CATEGORIES.find(c => c.name === name);
}
