import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import partytown from '@astrojs/partytown';

export default defineConfig({
  site: 'https://universoaquarista.com',
  output: 'static',
  trailingSlash: 'never',
  integrations: [
    sitemap(),
    partytown({ config: { forward: ['dataLayer.push'] } }),
  ],
});
