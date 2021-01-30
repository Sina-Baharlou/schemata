## [Classification by Attention: Scene Graph Classification with Prior Knowledge (AAAI 2021)](https://arxiv.org/abs/2011.10084)

#### by [Sahand Sharifzadeh](https://www.linkedin.com/in/sahandsharifzadeh/)<sup>1</sup>, [Sina Moayed Baharlou](https://www.sinabaharlou.com)<sup>2</sup>, [Volker Tresp](https://www.dbs.ifi.lmu.de/cms/personen/professoren/tresp/index.html)<sup>1,3</sup>
<sup>1 </sup> Ludwig Maximilian University, Munich, Germany, <sup>2 </sup> Sapienza University of Rome, Italy<br/>
<sup>3 </sup> Siemens AG, Munich, Germany<br/>

## Abstract
A major challenge in scene graph classification is that the appearance of objects and relations can be significantly different from one image to another. 
Previous works have addressed this by relational reasoning over all objects in an image or incorporating prior knowledge into classification. 
Unlike previous works, we do not consider separate models for perception and prior knowledge.
Instead, we take a multi-task learning approach, where we implement the classification as an attention layer. This allows for the prior knowledge to emerge and propagate within the perception model. By enforcing the model also to represent the prior, we achieve a strong inductive bias. 
We show that our model can accurately generate commonsense knowledge and that the iterative injection of this knowledge to scene representations leads to significantly higher classification performance. Additionally, our model can be fine-tuned on external knowledge given as triples. 
When combined with self-supervised learning and with 1% of annotated images only, this gives more than 3% improvement in object classification, 26% in scene graph classification, and 36% in predicate prediction accuracy.

## Model
<p align="center"><img src="docs/schema-architecture.png" title="Schema architecture."></p>
 

## Coming soon ...
