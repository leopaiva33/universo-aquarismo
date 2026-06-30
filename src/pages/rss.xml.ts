import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';

export async function GET(context: APIContext) {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  const sorted = posts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());

  return rss({
    title: 'Universo Aquarista',
    description: 'Guias completos sobre iluminação para aquário e aquarismo em geral.',
    site: context.site ?? 'https://universoaquarista.com',
    items: sorted.map(post => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      link: `/blog/${post.slug}/`,
    })),
    customData: `<language>pt-BR</language>`,
  });
}
