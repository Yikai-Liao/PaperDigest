---
layout: ../layouts/AboutLayout.astro
title: "About"
---

<div>
  <img src="/ai_reading.webp" class="sm:w-1/2 mx-auto" alt="coding dev illustration">
</div>

Paper Digest is a fully open-sourced project aim to help researchers and students to filter out the papers that they are interested in. 

For the recommendation system part, I simply use strategies similar to those from https://www.scholar-inbox.com:

1. I extracted the embeddings of all arxiv abstracts in cs and stat from 2017 and stored them in huggingsface dataset -- [ArxivEmbedding](https://huggingface.co/datasets/lyk/ArxivEmbedding). And this dataset will be updated every day according to Arxiv RSS feed. Two great open sourced embedding models are used to extract the embeddings on Github Actions:
    - [jasper_en_vision_language_v1](https://huggingface.co/NovaSearch/jasper_en_vision_language_v1)
    - [conan_v1](https://huggingface.co/TencentBAC/Conan-embedding-v1)

2. Then, I just follow scholar-inbox to train a simple logistic regression model to predict the probability of papers, while some more complex sampling strategies are used to make the model more robust. You could also have full control of all the hyper-parameters of the training and recommendation process.

3. Then, I leverage the monthly 150$ free credits from xAI (using Grok3) to generate the great summary of the recommended papers. I really thank Elon Musk for these free credits.

4. Finally, I use [Astro](https://astro.build) and the [AstroPaper Theme](https://astro-paper.pages.dev) to generate the static website, hosted on Vercel or Cloudflare. Of course, I use [giscus](https://github.com/giscus/giscus) to collect my labels to each new paper, which would be used in the next iteration of the recommendation system.

🥳 And I am very happy to say that, all the procedures above are totally free! Thanks for all these great free services!