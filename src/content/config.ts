import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: ({ image }) => z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    category: z.string().default('Aquarismo'),
    tags: z.array(z.string()).default([]),
    readTime: z.number().default(5),
    featured: z.boolean().default(false),
    draft: z.boolean().default(false),
    heroImage: image().optional(),
  }),
});

export const collections = { blog };
