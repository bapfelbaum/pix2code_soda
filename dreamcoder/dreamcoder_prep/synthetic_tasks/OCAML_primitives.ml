(* Define the type for a sample *)
type sample = int list

(* Function to filter samples by label *)
let filter_samples_by_label (samples : sample list) (desired_label : int) : sample list =
  List.filter (fun sample ->
    match sample with
    (* Check label per sample *)
    | [_; _; _; _; label] -> label = desired_label 
    (* Catch missmatched samples *)
    | _ -> false 
  ) samples

(* Example usage *)
let samples = [
  [216; 162; 218; 167; 1];
  [254; 151; 258; 154; 6];
  [265; 160; 268; 162; 5];
  [100; 200; 150; 250; 5];
  [300; 400; 350; 450; 3]
]

let desired_label = 5

let filtered_samples = filter_samples_by_label samples desired_label

(* Print the filtered samples *)
let () =
  List.iter (fun sample ->
    Printf.printf "[%d; %d; %d; %d; %d]\n" (List.nth sample 0) (List.nth sample 1) (List.nth sample 2) (List.nth sample 3) (List.nth sample 4)
  ) filtered_samples

