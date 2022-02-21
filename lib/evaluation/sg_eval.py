"""
Adapted from Danfei Xu. In particular, slow code was removed
"""
from collections import defaultdict

import numpy as np
import torch
from functools import reduce
from lib.pytorch_misc import intersect_2d, argsort_desc
#from lib.fpn.box_intersections_cpu.bbox import bbox_overlaps
from lib.fpn.box_utils import bbox_overlaps
from torchvision.ops import box_iou
from config import MODES
np.set_printoptions(precision=3)
import json

class BasicSceneGraphEvaluator:
    def __init__(self, mode, multiple_preds=False):
        self.result_dict = {}
        self.mode = mode
        self.result_dict[self.mode + '_recall'] = {20: [], 50: [], 100: [], 10000: []}
        self.result_dict['Q'] = {0: [], 1: [], 2: []}
        self.result_dict['mean'] = {0: []}
        self.result_dict[self.mode + '_recall_per_rel']= {20: [], 50: [], 100: [], 10000: []}
        self.result_dict['all_predictions']={'full_scores': [],'gt_rel_size': [],'pred_to_gt':[] }
        # self.result_dict[self.mode + 'filename'] = {20: [], 50: [], 100: []}
        self.multiple_preds = multiple_preds

        # -- (ADDED) Object recognition accuracy
        self.result_dict['obj_rec'] = []
        # -- (ADDED) Inverse-Zeroshot accuracy
        self.result_dict[self.mode + '_izs_recall'] = {20: [], 50: [], 100: [], 10000: []}
        self.result_dict[self.mode + '_izs_total'] = {'hits': 0, 'cnt': 0}

    @classmethod
    def all_modes(cls, **kwargs):
        evaluators = {m: cls(mode=m, **kwargs) for m in MODES}
        return evaluators

    @classmethod
    def vrd_modes(cls, **kwargs):
        evaluators = {m: cls(mode=m, multiple_preds=True, **kwargs) for m in ('preddet', 'phrdet')}
        return evaluators

    def evaluate_scene_graph_entry(self, gt_entry, pred_scores, viz_dict=None, iou_thresh=0.5, Q=None):
        res = evaluate_from_dict(gt_entry, pred_scores, self.mode, self.result_dict,
                                  viz_dict=viz_dict, iou_thresh=iou_thresh, multiple_preds=self.multiple_preds, Q=Q)
        # self.print_stats()
        return res

    def save(self, fn):
        np.save(fn, self.result_dict)

    def print_stats(self, epoch_num=None, writer=None, asm_num=1):
        # list_full_score = self.result_dict['all_predictions']['full_scores']
        # all_scores = np.concatenate(list_full_score)
        # Q = [[], [], []]
        # Q[0] = np.quantile(all_scores, .25)
        # Q[1] = np.quantile(all_scores, .50)
        # Q[2] = np.quantile(all_scores, .75)
        # mean_score = np.mean(all_scores)
        # for i, full_score in enumerate(list_full_score):
        #     Q_sc = [[], [], []]
        #     rec_i = [[], [], []]
        #     for c in range(3):
        #         Q_sc[c] = np.where(full_score > Q[c])
        #         if Q_sc[c][0].size != 0:
        #             last_ind = np.max(Q_sc[c])
        #         else:
        #             last_ind = 0
        #         match = reduce(np.union1d, self.result_dict['all_predictions']['pred_to_gt'][i][:last_ind + 1])
        #         rec_i[c] = float(len(match)) / self.result_dict['all_predictions']['gt_rel_size'][i]
        #         self.result_dict['Q'][c].append(rec_i[c])
        #
        #     mean_sc = np.where(full_score > mean_score)
        #     if mean_sc[0].size != 0:
        #         last_ind = np.max(mean_sc)
        #     else:
        #         last_ind = 0
        #     match = reduce(np.union1d, self.result_dict['all_predictions']['pred_to_gt'][i][:last_ind + 1])
        #     rec_i = float(len(match)) / self.result_dict['all_predictions']['gt_rel_size'][i]
        #     self.result_dict['mean'][0].append(rec_i)
        #
        # for k, v in self.result_dict['Q'].items():
        #     print('Q@%i: %f' % (k, np.mean(v)))
        #     if writer is not None:
        #         writer.add_scalar('Q data/Q@%i' % (k), np.mean(v), epoch_num)
        #
        # for k, v in self.result_dict['mean'].items():
        #     print('mean@%i: %f' % (k, np.mean(v)))
        #     if writer is not None:
        #         writer.add_scalar('Q data/mean@%i' % (k), np.mean(v), epoch_num)

        micro_accuracy = []
        print('======================' + self.mode + '============================')
        for k, v in self.result_dict[self.mode + '_recall'].items():
            if k == 'class_accuracy':
                print('Class Accuracy: ', np.mean(v))
                if writer is not None:
                    writer.add_scalar('class accuracy', np.mean(v), epoch_num)
            else:
                print('R@%i: %f' % (k, np.mean(v)))
                if writer is not None:
                    writer.add_scalar('Micro data/R@%i/asm@%i' % (k, asm_num), np.mean(v), epoch_num)
            micro_accuracy.append(np.mean(v))

        for k, vs in self.result_dict[self.mode + '_recall_per_rel'].items():
            detected_rel_per_image = []
            # filenames =[]
            local_fname = None
            acc_per_rel_per_batch = dict()
            macro_recall_per_rel = []
            total_batch_accuracy = []
            for v in vs:
                detected_rel = []
                hits_per_batch = 0
                gt_per_batch = 0
                for rel, (hits, gt_cnt) in v.items():
                    hits_per_batch += hits
                    gt_per_batch += gt_cnt
                    if rel in acc_per_rel_per_batch:
                        acc_per_rel_per_batch[rel].append(float(hits/gt_cnt))
                    else:
                        acc_per_rel_per_batch[rel] = [float(hits / gt_cnt)]
                    if hits > 0:
                        detected_rel.append(str(rel))
                    # local_fname = filename
                total_batch_accuracy.append(float(hits_per_batch) / float(gt_per_batch))
                detected_rel_per_image.append(detected_rel)
                # filenames.append(local_fname)
            for rel in acc_per_rel_per_batch.keys():
                macro_recall_per_rel.append(np.mean(acc_per_rel_per_batch[rel]))

            macro_recall = np.mean(macro_recall_per_rel)
            print('Macro R@%i: %f' % (k, macro_recall))
            with open('rel_per_image_vd.json', 'w', encoding='utf-8') as f:
                json.dump(detected_rel_per_image, f, ensure_ascii=False, indent=4)
            # with open('filenames.json', 'w', encoding='utf-8') as f:
            #     json.dump(filenames, f, ensure_ascii=False, indent=4)
            if writer is not None:
                writer.add_scalar('data/Macro R@%i/asm@%i' % (k, asm_num), macro_recall, epoch_num)

        # -- (ADDED) Object recognition accuracy
        print("Recognition accuracy: ", np.mean(self.result_dict['obj_rec']))
        if writer is not None:
            writer.add_scalar('data/ObjectRec/asm@%i' % (asm_num), np.mean(self.result_dict['obj_rec']), epoch_num)

        # -- (ADDED) Inverse-Zero shot accuracy
        for k, v in self.result_dict[self.mode + '_izs_recall'].items():
            if len(v) > 0:
                print('IZS R@%i: %f, #images: %d' % (k, np.mean(v), len(v)))

        hits = self.result_dict[self.mode + '_izs_total']['hits']
        cnt = self.result_dict[self.mode + '_izs_total']['cnt']
        if cnt > 0:
            print('IZS total accuracy: %f - %d/%d' % (float(hits)/float(cnt),hits,cnt))


def evaluate_from_dict(gt_entry, pred_entry, mode, result_dict, multiple_preds=False,
                       viz_dict=None, Q = None, **kwargs):
    """
    Shortcut to doing evaluate_recall from dict
    :param gt_entry: Dictionary containing gt_relations, gt_boxes, gt_classes
    :param pred_entry: Dictionary containing pred_rels, pred_boxes (if detection), pred_classes
    :param mode: 'det' or 'cls'
    :param result_dict: 
    :param viz_dict: 
    :param kwargs: 
    :return: 
    """
    gt_rels = gt_entry['gt_relations']
    gt_boxes = gt_entry['gt_boxes'].astype(float)
    gt_classes = gt_entry['gt_classes']
    # -- (ADDED) inverse-zeroshot triple indices
    izs_idx = gt_entry['izs_idx']

    pred_rel_inds = pred_entry['pred_rel_inds']
    rel_scores = pred_entry['rel_scores']

    if mode == 'predcls':
        pred_boxes = gt_boxes
        pred_classes = gt_classes
        obj_scores = np.ones(gt_classes.shape[0])
    elif mode == 'sgcls':
        pred_boxes = gt_boxes
        pred_classes = pred_entry['pred_classes']
        obj_scores = pred_entry['obj_scores']
    elif mode == 'sgdet' or mode == 'phrdet':
        pred_boxes = pred_entry['pred_boxes'].astype(float)
        pred_classes = pred_entry['pred_classes']
        obj_scores = pred_entry['obj_scores']
    elif mode == 'preddet':
        # Only extract the indices that appear in GT
        prc = intersect_2d(pred_rel_inds, gt_rels[:, :2])
        if prc.size == 0:
            for k in result_dict[mode + '_recall']:
                result_dict[mode + '_recall'][k].append(0.0)
            return None, None, None
        pred_inds_per_gt = prc.argmax(0)
        pred_rel_inds = pred_rel_inds[pred_inds_per_gt]
        rel_scores = rel_scores[pred_inds_per_gt]

        # Now sort the matching ones
        rel_scores_sorted = argsort_desc(rel_scores[:,1:])
        rel_scores_sorted[:,1] += 1
        rel_scores_sorted = np.column_stack((pred_rel_inds[rel_scores_sorted[:,0]], rel_scores_sorted[:,1]))

        matches = intersect_2d(rel_scores_sorted, gt_rels)
        for k in result_dict[mode + '_recall']:
            rec_i = float(matches[:k].any(0).sum()) / float(gt_rels.shape[0])
            result_dict[mode + '_recall'][k].append(rec_i)
        return None, None, None
    else:
        raise ValueError('invalid mode')

    if multiple_preds:
        obj_scores_per_rel = obj_scores[pred_rel_inds].prod(1)
        overall_scores = obj_scores_per_rel[:,None] * rel_scores[:,1:]
        score_inds = argsort_desc(overall_scores)#[:100]
        pred_rels = np.column_stack((pred_rel_inds[score_inds[:,0]], score_inds[:,1]+1))
        predicate_scores = rel_scores[score_inds[:,0], score_inds[:,1]+1]
    else:
        pred_rels = np.column_stack((pred_rel_inds, 1+rel_scores[:,1:].argmax(1)))
        predicate_scores = rel_scores[:,1:].max(1)

    pred_to_gt, pred_5ples, rel_scores = evaluate_recall(
                gt_rels, gt_boxes, gt_classes,
                pred_rels, pred_boxes, pred_classes,
                predicate_scores, obj_scores, phrdet= mode=='phrdet',
                **kwargs)

    for k in result_dict[mode + '_recall']:
        match = reduce(np.union1d, pred_to_gt[:k])
        # FIXME: I think this part of original code is wrong. We shouldn't do union.
        #: stores tuples (hits, count)
        hits_per_rel = dict()
        # gt_rels: shape: (m, 3), (s, p, r)
        for i in range(gt_rels.shape[0]):
            gt_s, gt_o, gt_r = gt_rels[i]
            hits_per_rel.setdefault(gt_r, [0, 0])
            hits_per_rel[gt_r][1] += 1
            hits_per_rel[gt_r][0] += i in match
        rec_per_rel = {r: (hits, cnt) for r, (hits, cnt) in hits_per_rel.items()}

        rec_i = float(len(match)) / float(gt_rels.shape[0])
        result_dict[mode + '_recall'][k].append(rec_i)
        result_dict[mode + '_recall_per_rel'][k].append(rec_per_rel)

        # -- (ADDED) calculate inverse-zeroshot recall accuracy
        if izs_idx is not None:
            izs_match = np.intersect1d(match, izs_idx)
            izs_acc = float(len(izs_match)) / float(len(izs_idx))
            result_dict[mode + '_izs_recall'][k].append(izs_acc)

    # -- (ADDED) calculate inverse-zeroshot overall accuracy (#total_hits/#total_triples)
    if izs_idx is not None:
        match_total = reduce(np.union1d, pred_to_gt)
        izs_match_total = np.intersect1d(match_total, izs_idx)
        result_dict[mode + '_izs_total']['hits'] += len(izs_match_total)
        result_dict[mode + '_izs_total']['cnt'] += len(izs_idx)

    # # New Score
    # full_score = np.prod(rel_scores, axis=1)
    # result_dict['all_predictions']['full_scores'].append(full_score)
    # result_dict['all_predictions']['gt_rel_size'].append(float(gt_rels.shape[0]))
    # result_dict['all_predictions']['pred_to_gt'].append(pred_to_gt)
    full_score = None #FIXME: just added this to void heavy computations of Q.

    # -- (ADDED) Determine object recognition accuracy
    # fixme is the definition correct?
    objs_tps = np.count_nonzero(np.array(gt_classes) == np.array(pred_classes)) # number of true positives
    objs_count = len(gt_classes)
    result_dict['obj_rec'].append(objs_tps/objs_count)

    # if mode in ('predcls', 'sgcls'):
    #     class_accuracy = (gt_classes == pred_classes).sum() / len(gt_classes)
    # else:
    #     ious = bbox_overlaps(pred_boxes, gt_boxes)
    #     is_match = (pred_classes[:, None] == gt_classes[None]) & (ious >= 0.5)
    #     class_accuracy = len(np.unique(np.argwhere(is_match)[:, 1])) / len(gt_classes)

    return pred_to_gt, pred_5ples, rel_scores, full_score

    # print(" ".join(["R@{:2d}: {:.3f}".format(k, v[-1]) for k, v in result_dict[mode + '_recall'].items()]))
    # Deal with visualization later
    # # Optionally, log things to a separate dictionary
    # if viz_dict is not None:
    #     # Caution: pred scores has changed (we took off the 0 class)
    #     gt_rels_scores = pred_scores[
    #         gt_rels[:, 0],
    #         gt_rels[:, 1],
    #         gt_rels[:, 2] - 1,
    #     ]
    #     # gt_rels_scores_cls = gt_rels_scores * pred_class_scores[
    #     #         gt_rels[:, 0]] * pred_class_scores[gt_rels[:, 1]]
    #
    #     viz_dict[mode + '_pred_rels'] = pred_5ples.tolist()
    #     viz_dict[mode + '_pred_rels_scores'] = max_pred_scores.tolist()
    #     viz_dict[mode + '_pred_rels_scores_cls'] = max_rel_scores.tolist()
    #     viz_dict[mode + '_gt_rels_scores'] = gt_rels_scores.tolist()
    #     viz_dict[mode + '_gt_rels_scores_cls'] = gt_rels_scores_cls.tolist()
    #
    #     # Serialize pred2gt matching as a list of lists, where each sublist is of the form
    #     # pred_ind, gt_ind1, gt_ind2, ....
    #     viz_dict[mode + '_pred2gt_rel'] = pred_to_gt


###########################
def evaluate_recall(gt_rels, gt_boxes, gt_classes,
                    pred_rels, pred_boxes, pred_classes, rel_scores=None, cls_scores=None,
                    iou_thresh=0.5, phrdet=False):
    """
    Evaluates the recall
    :param gt_rels: [#gt_rel, 3] array of GT relations
    :param gt_boxes: [#gt_box, 4] array of GT boxes
    :param gt_classes: [#gt_box] array of GT classes
    :param pred_rels: [#pred_rel, 3] array of pred rels. Assumed these are in sorted order
                      and refer to IDs in pred classes / pred boxes
                      (id0, id1, rel)
    :param pred_boxes:  [#pred_box, 4] array of pred boxes
    :param pred_classes: [#pred_box] array of predicted classes for these boxes
    :return: pred_to_gt: Matching from predicate to GT
             pred_5ples: the predicted (id0, id1, cls0, cls1, rel)
             rel_scores: [cls_0score, cls1_score, relscore]
                   """
    if pred_rels.size == 0:
        return [[]], np.zeros((0,5)), np.zeros(0)

    num_gt_boxes = gt_boxes.shape[0]
    num_gt_relations = gt_rels.shape[0]
    assert num_gt_relations != 0

    gt_triplets, gt_triplet_boxes, _ = _triplet(gt_rels[:, 2],
                                                gt_rels[:, :2],
                                                gt_classes,
                                                gt_boxes)
    num_boxes = pred_boxes.shape[0]
    assert pred_rels[:,:2].max() < pred_classes.shape[0]

    # Exclude self rels
    # assert np.all(pred_rels[:,0] != pred_rels[:,1])
    assert np.all(pred_rels[:,2] > 0)

    pred_triplets, pred_triplet_boxes, relation_scores = \
        _triplet(pred_rels[:,2], pred_rels[:,:2], pred_classes, pred_boxes,
                 rel_scores, cls_scores)

    scores_overall = relation_scores.prod(1)
    #FIXME: (SAHAND) I disabled this error after the uncertainty for now. Bring it back later.
    # if not np.all(scores_overall[1:] <= scores_overall[:-1] + 1e-5):
    #     print("Somehow the relations weren't sorted properly: \n{}".format(scores_overall))
        # raise ValueError("Somehow the relations werent sorted properly")

    # Compute recall. It's most efficient to match once and then do recall after
    pred_to_gt = _compute_pred_matches(
        gt_triplets,
        pred_triplets,
        gt_triplet_boxes,
        pred_triplet_boxes,
        iou_thresh,
        phrdet=phrdet,
    )

    # Contains some extra stuff for visualization. Not needed.
    pred_5ples = np.column_stack((
        pred_rels[:,:2],
        pred_triplets[:, [0, 2, 1]],
    ))

    return pred_to_gt, pred_5ples, relation_scores


def _triplet(predicates, relations, classes, boxes,
             predicate_scores=None, class_scores=None):
    """
    format predictions into triplets
    :param predicates: A 1d numpy array of num_boxes*(num_boxes-1) predicates, corresponding to
                       each pair of possibilities
    :param relations: A (num_boxes*(num_boxes-1), 2) array, where each row represents the boxes
                      in that relation
    :param classes: A (num_boxes) array of the classes for each thing.
    :param boxes: A (num_boxes,4) array of the bounding boxes for everything.
    :param predicate_scores: A (num_boxes*(num_boxes-1)) array of the scores for each predicate
    :param class_scores: A (num_boxes) array of the likelihood for each object.
    :return: Triplets: (num_relations, 3) array of class, relation, class
             Triplet boxes: (num_relation, 8) array of boxes for the parts
             Triplet scores: num_relation array of the scores overall for the triplets
    """
    assert (predicates.shape[0] == relations.shape[0])

    sub_ob_classes = classes[relations[:, :2]]
    triplets = np.column_stack((sub_ob_classes[:, 0], predicates, sub_ob_classes[:, 1]))
    triplet_boxes = np.column_stack((boxes[relations[:, 0]], boxes[relations[:, 1]]))

    triplet_scores = None
    if predicate_scores is not None and class_scores is not None:
        triplet_scores = np.column_stack((
            class_scores[relations[:, 0]],
            class_scores[relations[:, 1]],
            predicate_scores,
        ))

    return triplets, triplet_boxes, triplet_scores


def _compute_pred_matches(gt_triplets, pred_triplets,
                 gt_boxes, pred_boxes, iou_thresh, phrdet=False):
    """
    Given a set of predicted triplets, return the list of matching GT's for each of the
    given predictions
    :param gt_triplets: 
    :param pred_triplets: 
    :param gt_boxes: 
    :param pred_boxes: 
    :param iou_thresh: 
    :return: 
    """
    # This performs a matrix multiplication-esque thing between the two arrays
    # Instead of summing, we want the equality, so we reduce in that way
    # The rows correspond to GT triplets, columns to pred triplets
    keeps = intersect_2d(gt_triplets, pred_triplets)
    gt_has_match = keeps.any(1)
    pred_to_gt = [[] for x in range(pred_boxes.shape[0])]
    for gt_ind, gt_box, keep_inds in zip(np.where(gt_has_match)[0],
                                         gt_boxes[gt_has_match],
                                         keeps[gt_has_match],
                                         ):
        boxes = pred_boxes[keep_inds]
        if phrdet:
            # Evaluate where the union box > 0.5
            gt_box_union = gt_box.reshape((2, 4))
            gt_box_union = np.concatenate((gt_box_union.min(0)[:2], gt_box_union.max(0)[2:]), 0)

            box_union = boxes.reshape((-1, 2, 4))
            box_union = np.concatenate((box_union.min(1)[:,:2], box_union.max(1)[:,2:]), 1)

            inds = bbox_overlaps(gt_box_union[None], box_union)[0] >= iou_thresh

        else:
            # sub_iou = box_iou(torch.tensor(gt_box[None,:4]), torch.tensor(boxes[:,:4]))
            sub_iou = bbox_overlaps(gt_box[None,:4], boxes[:, :4])[0]
            # obj_iou = box_iou(torch.tensor(gt_box[None,4:]), torch.tensor(boxes[:,4:]))
            obj_iou = bbox_overlaps(gt_box[None,4:], boxes[:, 4:])[0]

            inds = (sub_iou >= iou_thresh) & (obj_iou >= iou_thresh)

        for i in np.where(keep_inds)[0][inds]:
            pred_to_gt[i].append(int(gt_ind))
    return pred_to_gt
