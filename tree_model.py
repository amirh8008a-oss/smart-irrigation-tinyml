# MicroPython Decision Tree Model (Generated automatically)
# Total Nodes: 125 | Leaf Nodes: 63 | Max Depth: 8
# Input: x is a list of 23 float features ordered via feature_order.json

def predict_tree(x):
    if x[1] <= 24.500000:
        if x[2] <= 78.549999:
            if x[0] <= 49.000000:
                return 1
            else:
                return 0
        else:
            if x[2] <= 79.950001:
                if x[2] <= 79.850002:
                    return 0
                else:
                    if x[7] <= 0.500000:
                        if x[22] <= 0.500000:
                            return 1
                        else:
                            return 0
                    else:
                        return 0
            else:
                if x[1] <= 23.500000:
                    return 0
                else:
                    if x[2] <= 80.250000:
                        if x[19] <= 0.500000:
                            return 0
                        else:
                            if x[0] <= 10.500000:
                                if x[0] <= 7.500000:
                                    return 0
                                else:
                                    return 2
                            else:
                                return 0
                    else:
                        if x[2] <= 80.750000:
                            if x[19] <= 0.500000:
                                if x[9] <= 0.500000:
                                    return 0
                                else:
                                    return 1
                            else:
                                return 2
                        else:
                            return 0
    else:
        if x[0] <= 69.500000:
            if x[0] <= 15.500000:
                if x[0] <= 10.500000:
                    if x[0] <= 8.500000:
                        return 2
                    else:
                        if x[11] <= 0.500000:
                            return 2
                        else:
                            if x[1] <= 32.500000:
                                return 1
                            else:
                                return 2
                else:
                    if x[1] <= 30.500000:
                        if x[14] <= 0.500000:
                            if x[2] <= 78.549999:
                                return 1
                            else:
                                if x[2] <= 79.750000:
                                    return 0
                                else:
                                    return 1
                        else:
                            if x[1] <= 28.500000:
                                if x[0] <= 11.500000:
                                    return 2
                                else:
                                    return 1
                            else:
                                return 2
                    else:
                        if x[11] <= 0.500000:
                            return 2
                        else:
                            if x[0] <= 13.500000:
                                if x[1] <= 32.500000:
                                    return 1
                                else:
                                    return 2
                            else:
                                return 1
            else:
                if x[0] <= 59.500000:
                    if x[0] <= 49.500000:
                        if x[17] <= 0.500000:
                            if x[2] <= 80.299999:
                                if x[2] <= 78.500000:
                                    return 1
                                else:
                                    return 1
                            else:
                                if x[0] <= 27.000000:
                                    return 1
                                else:
                                    return 0
                        else:
                            if x[7] <= 0.500000:
                                if x[2] <= 80.450001:
                                    return 1
                                else:
                                    return 0
                            else:
                                if x[0] <= 35.500000:
                                    return 1
                                else:
                                    return 0
                    else:
                        if x[7] <= 0.500000:
                            if x[20] <= 0.500000:
                                return 1
                            else:
                                if x[11] <= 0.500000:
                                    return 1
                                else:
                                    return 0
                        else:
                            if x[17] <= 0.500000:
                                if x[21] <= 0.500000:
                                    return 1
                                else:
                                    return 0
                            else:
                                return 0
                else:
                    if x[7] <= 0.500000:
                        if x[20] <= 0.500000:
                            if x[2] <= 80.450001:
                                if x[22] <= 0.500000:
                                    return 1
                                else:
                                    return 1
                            else:
                                return 0
                        else:
                            return 0
                    else:
                        if x[17] <= 0.500000:
                            if x[21] <= 0.500000:
                                if x[22] <= 0.500000:
                                    return 1
                                else:
                                    return 0
                            else:
                                return 0
                        else:
                            return 0
        else:
            if x[0] <= 79.500000:
                if x[4] <= 0.500000:
                    if x[17] <= 0.500000:
                        if x[0] <= 70.500000:
                            if x[6] <= 0.500000:
                                return 0
                            else:
                                if x[12] <= 0.500000:
                                    return 1
                                else:
                                    return 0
                        else:
                            return 0
                    else:
                        if x[7] <= 0.500000:
                            return 1
                        else:
                            return 0
                else:
                    if x[17] <= 0.500000:
                        return 1
                    else:
                        return 0
            else:
                if x[0] <= 80.500000:
                    if x[4] <= 0.500000:
                        return 0
                    else:
                        if x[17] <= 0.500000:
                            return 1
                        else:
                            return 0
                else:
                    return 0
