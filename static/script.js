$(document).ready(function(){
    // Récupérer la valeur sélectionnée du sous-groupe
    var selectedSubgroup = $("#id_subgroup").val();
        
    // Faire une requête AJAX pour obtenir les types de services en fonction du sous-groupe
    $.ajax({
        url: "/get_types_services/" + selectedSubgroup, // Créez une route Flask pour gérer cette requête
        type: "GET",
        success: function(response){
            // Mettez à jour les options de la liste déroulante des types de services
            $("#types_services").html(response);
        },
        error: function(error){
            console.log("Erreur AJAX:", error);
        }
    })
    // Attacher un gestionnaire d'événements au changement de sélection du sous-groupe
    $("#id_subgroup").change(function(){
        // Récupérer la valeur sélectionnée du sous-groupe
        var selectedSubgroup = $(this).val();
        
        // Faire une requête AJAX pour obtenir les types de services en fonction du sous-groupe
        $.ajax({
            url: "/get_types_services/" + selectedSubgroup, // Créez une route Flask pour gérer cette requête
            type: "GET",
            success: function(response){
                // Mettez à jour les options de la liste déroulante des types de services
                $("#types_services").html(response);
            },
            error: function(error){
                console.log("Erreur AJAX:", error);
            }
        });
    });
});
